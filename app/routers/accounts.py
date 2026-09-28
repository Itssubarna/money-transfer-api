from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app import services
from app.db import get_session
from app.schemas.account import AccountCreate, AccountRead
from app.schemas.error import error_responses

router = APIRouter(tags=["accounts"])

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.post(
    "/accounts",
    response_model=AccountRead,
    status_code=201,
    responses=error_responses(422),
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
    responses=error_responses(404, 422),
)
def get_account(
    account_id: Annotated[int, Path(gt=0)],
    session: DatabaseSession,
) -> AccountRead:
    account = services.get_account(session, account_id)
    return AccountRead.model_validate(account)
