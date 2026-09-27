from sqlalchemy.orm import Session

from app.db.models import Account
from app.schemas.account import AccountCreate


def create_account(
    session: Session,
    data: AccountCreate,
) -> Account:
    account = Account(
        name=data.name,
        balance=data.initial_balance,
    )

    session.add(account)
    session.commit()
    session.refresh(account)

    return account