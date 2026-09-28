"""Unit tests for the transfer service, called directly with a DB session."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Account, Transfer
from app.errors import AppError, BusinessRuleError, ConflictError, NotFoundError
from app.schemas.transfer import TransferCreate
from app.services import transfer_money


def make_accounts(session: Session, *balances: int) -> list[int]:
    accounts = [Account(name=f"acc{i}", balance=b) for i, b in enumerate(balances)]
    session.add_all(accounts)
    session.commit()
    ids = [a.id for a in accounts]
    # Reading ids after commit autobegins a transaction; end it, because
    # transfer_money() opens its own with session.begin().
    session.commit()
    return ids


def balances(session: Session, *ids: int) -> list[int]:
    session.expire_all()
    return [session.get(Account, i).balance for i in ids]


def transfer_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Transfer))


def test_moves_money_and_records_transfer(session):
    a, b = make_accounts(session, 1000, 0)

    transfer, created = transfer_money(
        session, TransferCreate(from_account_id=a, to_account_id=b, amount=300), None
    )

    assert created is True
    assert transfer.amount == 300
    assert balances(session, a, b) == [700, 300]
    assert transfer_count(session) == 1


def test_allows_transferring_entire_balance(session):
    a, b = make_accounts(session, 500, 0)

    transfer_money(
        session, TransferCreate(from_account_id=a, to_account_id=b, amount=500), None
    )

    assert balances(session, a, b) == [0, 500]


@pytest.mark.parametrize(
    ("amount", "sender", "receiver", "error", "code"),
    [
        (101, "a", "b", BusinessRuleError, "INSUFFICIENT_FUNDS"),
        (10, "a", "a", BusinessRuleError, "SAME_ACCOUNT"),
        (10, "missing", "b", NotFoundError, "SENDER_NOT_FOUND"),
        (10, "a", "missing", NotFoundError, "RECEIVER_NOT_FOUND"),
    ],
)
def test_failed_transfer_rolls_back_everything(
    session, amount, sender, receiver, error, code
):
    a, b = make_accounts(session, 100, 50)
    ids = {"a": a, "b": b, "missing": 9999}

    with pytest.raises(AppError) as exc:
        transfer_money(
            session,
            TransferCreate(
                from_account_id=ids[sender], to_account_id=ids[receiver], amount=amount
            ),
            None,
        )

    assert type(exc.value) is error
    assert exc.value.code == code
    assert balances(session, a, b) == [100, 50]
    assert transfer_count(session) == 0


def test_idempotency_key_replay_returns_original_without_moving_money(session):
    a, b = make_accounts(session, 1000, 0)
    data = TransferCreate(from_account_id=a, to_account_id=b, amount=100)

    first, first_created = transfer_money(session, data, "key-1")
    second, second_created = transfer_money(session, data, "key-1")

    assert (first_created, second_created) == (True, False)
    assert first.id == second.id
    assert balances(session, a, b) == [900, 100]
    assert transfer_count(session) == 1


def test_idempotency_key_reuse_with_different_request_conflicts(session):
    a, b = make_accounts(session, 1000, 0)
    transfer_money(
        session, TransferCreate(from_account_id=a, to_account_id=b, amount=100), "k"
    )

    with pytest.raises(ConflictError):
        transfer_money(
            session, TransferCreate(from_account_id=a, to_account_id=b, amount=1), "k"
        )

    assert balances(session, a, b) == [900, 100]
    assert transfer_count(session) == 1


def test_different_idempotency_keys_create_separate_transfers(session):
    a, b = make_accounts(session, 1000, 0)
    data = TransferCreate(from_account_id=a, to_account_id=b, amount=100)

    transfer_money(session, data, "key-1")
    transfer_money(session, data, "key-2")

    assert balances(session, a, b) == [800, 200]
    assert transfer_count(session) == 2


def test_database_rejects_negative_balance(session):
    """The CHECK constraint is the last line of defence against overdrafts."""
    (a,) = make_accounts(session, 10)
    session.get(Account, a).balance = -1

    with pytest.raises(Exception, match="balance_nonnegative|CHECK constraint"):
        session.commit()
