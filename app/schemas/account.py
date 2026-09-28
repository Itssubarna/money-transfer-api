from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


# Integer minor units (e.g. cents). The cap keeps values far below
# SQLite's 64-bit INTEGER limit.
MAX_MINOR_UNITS = 10**15

NonnegativeMoney = Annotated[
    StrictInt,
    Field(ge=0, le=MAX_MINOR_UNITS),
]


class AccountCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    initial_balance: NonnegativeMoney = 0

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("name cannot be blank")

        return value


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    balance: int
    created_at: datetime