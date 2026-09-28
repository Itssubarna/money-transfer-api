from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db.models import Account, Transfer


def get_account(
    session: Session,
    account_id: int,
) -> Account | None:
    return session.get(Account, account_id)


def create_account(
    session: Session,
    name: str,
    balance: int,
) -> Account:
    account = Account(name=name, balance=balance)
    session.add(account)
    session.flush()
    return account


def get_transfer_by_key(
    session: Session,
    key: str,
) -> Transfer | None:
    return session.scalar(
        select(Transfer).where(
            Transfer.idempotency_key == key
        )
    )


def debit(
    session: Session,
    account_id: int,
    amount: int,
) -> bool:
    """Subtract ``amount`` only if the balance covers it.

    The check and the write are a single UPDATE, so no other transaction
    can change the balance in between. Returns False if funds are short.
    """
    result = session.execute(
        update(Account)
        .where(
            Account.id == account_id,
            Account.balance >= amount,
        )
        .values(balance=Account.balance - amount)
    )
    return result.rowcount == 1


def credit(
    session: Session,
    account_id: int,
    amount: int,
) -> None:
    session.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(balance=Account.balance + amount)
    )


def create_transfer(
    session: Session,
    from_account_id: int,
    to_account_id: int,
    amount: int,
    idempotency_key: str | None,
) -> Transfer:
    transfer = Transfer(
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        idempotency_key=idempotency_key,
    )
    session.add(transfer)
    session.flush()
    return transfer


def list_transactions(
    session: Session,
    account_id: int,
    limit: int,
    offset: int,
) -> list[Transfer]:
    statement = (
        select(Transfer)
        .where(
            or_(
                Transfer.from_account_id == account_id,
                Transfer.to_account_id == account_id,
            )
        )
        .order_by(
            Transfer.created_at.desc(),
            Transfer.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return list(session.scalars(statement))
