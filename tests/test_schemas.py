"""Unit tests for request validation (no database, no HTTP)."""

import pytest
from pydantic import ValidationError

from app.schemas.account import AccountCreate
from app.schemas.transfer import TransferCreate


class TestAccountCreate:
    def test_defaults_initial_balance_to_zero(self):
        assert AccountCreate(name="Alice").initial_balance == 0

    def test_strips_name(self):
        assert AccountCreate(name="  Alice  ").name == "Alice"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 101])
    def test_rejects_invalid_name(self, name):
        with pytest.raises(ValidationError):
            AccountCreate(name=name)

    @pytest.mark.parametrize("balance", [-1, 10.5, "100", True, None])
    def test_rejects_invalid_initial_balance(self, balance):
        with pytest.raises(ValidationError):
            AccountCreate(name="Alice", initial_balance=balance)


class TestTransferCreate:
    def test_accepts_valid_transfer(self):
        transfer = TransferCreate(from_account_id=1, to_account_id=2, amount=500)
        assert transfer.amount == 500

    @pytest.mark.parametrize("amount", [0, -1, 1.5, "10", True])
    def test_rejects_invalid_amount(self, amount):
        with pytest.raises(ValidationError):
            TransferCreate(from_account_id=1, to_account_id=2, amount=amount)

    @pytest.mark.parametrize("field", ["from_account_id", "to_account_id"])
    @pytest.mark.parametrize("value", [0, -5, "1"])
    def test_rejects_invalid_account_ids(self, field, value):
        payload = {"from_account_id": 1, "to_account_id": 2, "amount": 1}
        payload[field] = value
        with pytest.raises(ValidationError):
            TransferCreate(**payload)
