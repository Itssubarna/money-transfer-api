from sqlalchemy.orm import Session

from app.db import crud, write_transaction
from app.db.models import Account, Transfer
from app.errors import NotFoundError
from app.schemas.account import AccountCreate


def create_account(
    session: Session,
    data: AccountCreate,
) -> Account:
    with write_transaction(session):
        return crud.create_account(
            session,
            name=data.name,
            balance=data.initial_balance,
        )


def get_account(
    session: Session,
    account_id: int,
) -> Account:
    account = crud.get_account(session, account_id)

    if account is None:
        raise NotFoundError(
            "ACCOUNT_NOT_FOUND",
            "Account not found",
        )

    return account


def get_account_transactions(
    session: Session,
    account_id: int,
    limit: int,
    offset: int,
) -> list[Transfer]:
    get_account(session, account_id)
    return crud.list_transactions(session, account_id, limit, offset)
