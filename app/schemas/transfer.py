from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


PositiveMoney = Annotated[
    StrictInt,
    Field(gt=0),
]

AccountId = Annotated[
    StrictInt,
    Field(gt=0),
]


class TransferCreate(BaseModel):
    from_account_id: AccountId
    to_account_id: AccountId
    amount: PositiveMoney
    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )


class TransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_account_id: int
    to_account_id: int
    amount: int
    created_at: datetime


class TransactionRead(TransferRead):
    direction: Literal["debit", "credit"]


class TransactionPage(BaseModel):
    items: list[TransactionRead]
    limit: int
    offset: int