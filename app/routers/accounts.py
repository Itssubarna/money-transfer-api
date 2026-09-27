from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app import crud, services
from app.db import get_session
from app.errors import ApiError
from app.schemas.account import AccountCreate, AccountRead

router = APIRouter()

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.post(
    "/accounts",
    response_model=AccountRead,
    status_code=201,
)
def create_account(
    data: AccountCreate,
    session: DatabaseSession,
) -> AccountRead:
    account = services.create_account(session, data)
    return AccountRead.model_validate(account)


@router.get(
    "/accounts/{account_id}",
    response_model=AccountRead,
)
def get_account(
    account_id: Annotated[int, Path(gt=0)],
    session: DatabaseSession,
) -> AccountRead:
    account = crud.get_account(session, account_id)

    if account is None:
        raise ApiError(
            404,
            "ACCOUNT_NOT_FOUND",
            "Account not found",
        )

    return AccountRead.model_validate(account)