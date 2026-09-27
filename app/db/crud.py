from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Account, Transfer


def get_account(
    session: Session,
    account_id: int,
) -> Account | None:
    return session.get(Account, account_id)


def get_transfer_by_key(
    session: Session,
    key: str,
) -> Transfer | None:
    return session.scalar(
        select(Transfer).where(
            Transfer.idempotency_key == key
        )
    )


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