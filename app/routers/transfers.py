from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app import crud
from app.db import get_session
from app.errors import ApiError
from app.schemas.transfer import (
    TransactionPage,
    TransactionRead,
    TransferRead,
)

router = APIRouter()

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=TransactionPage,
)
def get_transactions(
    account_id: Annotated[int, Path(gt=0)],
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:

    if crud.get_account(session, account_id) is None:
        raise ApiError(
            404,
            "ACCOUNT_NOT_FOUND",
            "Account not found",
        )

    transfers = crud.list_transactions(
        session,
        account_id,
        limit,
        offset,
    )

    items = [
        TransactionRead(
            **TransferRead.model_validate(transfer).model_dump(),
            direction=(
                "debit"
                if transfer.from_account_id == account_id
                else "credit"
            ),
        )
        for transfer in transfers
    ]

    return TransactionPage(
        items=items,
        limit=limit,
        offset=offset,
    )