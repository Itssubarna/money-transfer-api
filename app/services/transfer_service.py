from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import Account, Transfer
from app.errors import ApiError
from app.schemas.transfer import TransferCreate


def transfer_money(
    session: Session,
    data: TransferCreate,
    idempotency_key: str | None,
) -> tuple[Transfer, bool]:

    if data.from_account_id == data.to_account_id:
        raise ApiError(
            400,
            "SAME_ACCOUNT",
            "Sender and receiver must be different accounts",
        )

    try:
        with session.begin():
            if idempotency_key:
                existing = crud.get_transfer_by_key(
                    session,
                    idempotency_key,
                )

                if existing:
                    return existing, False

            sender = session.get(Account, data.from_account_id)

            if sender is None:
                raise ApiError(
                    404,
                    "SENDER_NOT_FOUND",
                    "Sender account not found",
                )

            receiver = session.get(Account, data.to_account_id)

            if receiver is None:
                raise ApiError(
                    404,
                    "RECEIVER_NOT_FOUND",
                    "Receiver account not found",
                )

            if sender.balance < data.amount:
                raise ApiError(
                    400,
                    "INSUFFICIENT_FUNDS",
                    "Insufficient account balance",
                )

            sender.balance -= data.amount
            receiver.balance += data.amount

            transfer = Transfer(
                from_account_id=sender.id,
                to_account_id=receiver.id,
                amount=data.amount,
                idempotency_key=idempotency_key,
            )

            session.add(transfer)
            session.flush()

            return transfer, True

    except ApiError:
        raise