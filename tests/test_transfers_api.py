"""Integration tests for POST /transfers."""

import pytest


def transfer(client, from_id, to_id, amount, key=None):
    headers = {"Idempotency-Key": key} if key is not None else {}
    return client.post(
        "/transfers",
        json={"from_account_id": from_id, "to_account_id": to_id, "amount": amount},
        headers=headers,
    )


def test_successful_transfer(client, create_account, get_balance):
    a = create_account("Alice", 1000)
    b = create_account("Bob", 0)

    response = transfer(client, a["id"], b["id"], 250)

    assert response.status_code == 201
    body = response.json()
    assert body["from_account_id"] == a["id"]
    assert body["to_account_id"] == b["id"]
    assert body["amount"] == 250
    assert get_balance(a["id"]) == 750
    assert get_balance(b["id"]) == 250


def test_insufficient_funds(client, create_account, get_balance):
    a = create_account("Alice", 100)
    b = create_account("Bob", 0)

    response = transfer(client, a["id"], b["id"], 101)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INSUFFICIENT_FUNDS"
    assert get_balance(a["id"]) == 100
    assert get_balance(b["id"]) == 0


def test_same_account_transfer_rejected(client, create_account, get_balance):
    a = create_account("Alice", 100)

    response = transfer(client, a["id"], a["id"], 10)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SAME_ACCOUNT"
    assert get_balance(a["id"]) == 100


def test_unknown_sender(client, create_account):
    b = create_account("Bob", 0)

    response = transfer(client, 9999, b["id"], 10)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SENDER_NOT_FOUND"


def test_unknown_receiver(client, create_account, get_balance):
    a = create_account("Alice", 100)

    response = transfer(client, a["id"], 9999, 10)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECEIVER_NOT_FOUND"
    assert get_balance(a["id"]) == 100


@pytest.mark.parametrize("amount", [0, -10, 10.5, "10", None, 10**15 + 1, 2**64])
def test_invalid_amount_rejected(client, create_account, amount):
    a = create_account("Alice", 100)
    b = create_account("Bob", 0)

    response = transfer(client, a["id"], b["id"], amount)

    assert response.status_code == 422


def test_missing_fields_rejected(client):
    response = client.post("/transfers", json={"amount": 10})

    assert response.status_code == 422


class TestIdempotency:
    def test_replay_returns_same_transfer_and_moves_money_once(
        self, client, create_account, get_balance
    ):
        a = create_account("Alice", 1000)
        b = create_account("Bob", 0)

        first = transfer(client, a["id"], b["id"], 100, key="abc-123")
        second = transfer(client, a["id"], b["id"], 100, key="abc-123")

        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json() == second.json()
        assert get_balance(a["id"]) == 900
        assert get_balance(b["id"]) == 100

    def test_requests_without_key_are_not_deduplicated(
        self, client, create_account, get_balance
    ):
        a = create_account("Alice", 1000)
        b = create_account("Bob", 0)

        assert transfer(client, a["id"], b["id"], 100).status_code == 201
        assert transfer(client, a["id"], b["id"], 100).status_code == 201
        assert get_balance(a["id"]) == 800

    def test_blank_key_rejected(self, client, create_account):
        a = create_account("Alice", 1000)
        b = create_account("Bob", 0)

        response = transfer(client, a["id"], b["id"], 100, key="   ")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"

    def test_too_long_key_rejected(self, client, create_account):
        a = create_account("Alice", 1000)
        b = create_account("Bob", 0)

        response = transfer(client, a["id"], b["id"], 100, key="k" * 256)

        assert response.status_code == 422

    def test_failed_request_does_not_consume_key(
        self, client, create_account, get_balance
    ):
        a = create_account("Alice", 50)
        b = create_account("Bob", 0)

        assert transfer(client, a["id"], b["id"], 100, key="retry").status_code == 400
        assert transfer(client, a["id"], b["id"], 50, key="retry").status_code == 201
        assert get_balance(b["id"]) == 50

    def test_reusing_key_with_different_payload_is_rejected(
        self, client, create_account, get_balance
    ):
        """A reused key with a different body is a client bug; silently
        returning the old transfer would hide it."""
        a = create_account("Alice", 1000)
        b = create_account("Bob", 0)

        assert transfer(client, a["id"], b["id"], 100, key="k1").status_code == 201
        response = transfer(client, a["id"], b["id"], 999, key="k1")

        assert response.status_code == 409
        assert get_balance(a["id"]) == 900


class TestErrorFormat:
    """Every error shares one envelope so clients can parse it."""

    def test_business_and_validation_errors_share_a_shape(self, client, create_account):
        a = create_account("Alice", 10)
        b = create_account("Bob", 0)

        business = transfer(client, a["id"], b["id"], 1000).json()
        validation = transfer(client, a["id"], b["id"], -1).json()
        not_found = client.get("/accounts/9999").json()
        unknown_route = client.get("/nope").json()

        for body in (business, validation, not_found, unknown_route):
            assert body.keys() == {"error"}, body
            assert {"code", "message"} <= body["error"].keys(), body

    def test_validation_error_lists_offending_fields(self, client):
        response = client.post(
            "/transfers",
            json={"from_account_id": 1, "to_account_id": 2, "amount": -1},
        )

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert [d["field"] for d in error["details"]] == ["body.amount"]

    def test_key_reuse_error_code(self, client, create_account):
        a = create_account("Alice", 1000)
        b = create_account("Bob", 0)
        transfer(client, a["id"], b["id"], 100, key="k1")

        response = transfer(client, a["id"], b["id"], 5, key="k1")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
