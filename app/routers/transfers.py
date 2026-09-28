from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from sqlalchemy.orm import Session

from app import services
from app.db import get_session
from app.errors import InvalidRequestError
from app.schemas.error import error_responses
from app.schemas.transfer import (
    TransactionPage,
    TransactionRead,
    TransferCreate,
    TransferRead,
)

router = APIRouter(tags=["transfers"])

DatabaseSession = Annotated[
    Session,
    Depends(get_session),
]


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=TransactionPage,
    responses=error_responses(404, 422),
)
def get_transactions(
    account_id: Annotated[int, Path(gt=0)],
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    transfers = services.get_account_transactions(
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


@router.post(
    "/transfers",
    response_model=TransferRead,
    status_code=201,
    responses={
        200: {
            "model": TransferRead,
            "description": "Replay of an earlier request with the same Idempotency-Key",
        },
        **error_responses(400, 404, 409, 422),
    },
)
def create_transfer(
    data: TransferCreate,
    session: DatabaseSession,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(
            max_length=255,
            description="Optional client-generated key; retries with the "
            "same key and body return the original transfer.",
        ),
    ] = None,
) -> TransferRead:

    if (
        idempotency_key is not None
        and not idempotency_key.strip()
    ):
        raise InvalidRequestError(
            "INVALID_IDEMPOTENCY_KEY",
            "Idempotency-Key cannot be blank",
        )

    transfer, created = services.transfer_money(
        session,
        data,
        idempotency_key,
    )

    if not created:
        response.status_code = 200

    return TransferRead.model_validate(transfer)
