from sqlalchemy.orm import Session

from app.db import crud, write_transaction
from app.db.models import Transfer
from app.errors import BusinessRuleError, ConflictError, NotFoundError
from app.schemas.transfer import TransferCreate


def transfer_money(
    session: Session,
    data: TransferCreate,
    idempotency_key: str | None,
) -> tuple[Transfer, bool]:
    """Move money between two accounts atomically.

    Returns ``(transfer, created)``; ``created`` is False when an earlier
    transfer with the same idempotency key is being replayed.

    The whole operation runs inside ``write_transaction``, which holds
    SQLite's write lock, so concurrent transfers (and concurrent retries
    with the same idempotency key) are applied one after another.
    """

    if data.from_account_id == data.to_account_id:
        raise BusinessRuleError(
            "SAME_ACCOUNT",
            "Sender and receiver must be different accounts",
        )

    with write_transaction(session):
        if idempotency_key:
            existing = crud.get_transfer_by_key(
                session,
                idempotency_key,
            )

            if existing:
                _ensure_same_request(existing, data)
                return existing, False

        if crud.get_account(session, data.from_account_id) is None:
            raise NotFoundError(
                "SENDER_NOT_FOUND",
                "Sender account not found",
            )

        if crud.get_account(session, data.to_account_id) is None:
            raise NotFoundError(
                "RECEIVER_NOT_FOUND",
                "Receiver account not found",
            )

        if not crud.debit(session, data.from_account_id, data.amount):
            raise BusinessRuleError(
                "INSUFFICIENT_FUNDS",
                "Insufficient account balance",
            )

        crud.credit(session, data.to_account_id, data.amount)

        transfer = crud.create_transfer(
            session,
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=data.amount,
            idempotency_key=idempotency_key,
        )

        return transfer, True


def _ensure_same_request(existing: Transfer, data: TransferCreate) -> None:
    if (
        existing.from_account_id,
        existing.to_account_id,
        existing.amount,
    ) != (
        data.from_account_id,
        data.to_account_id,
        data.amount,
    ):
        raise ConflictError(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key was already used with a different request",
        )
