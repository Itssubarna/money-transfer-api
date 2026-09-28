"""Integration tests for the /accounts endpoints."""

import pytest


def test_create_account(client):
    response = client.post("/accounts", json={"name": "Alice", "initial_balance": 1000})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice"
    assert body["balance"] == 1000
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_account_defaults_balance_to_zero(client):
    response = client.post("/accounts", json={"name": "Bob"})

    assert response.status_code == 201
    assert response.json()["balance"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"name": "Alice", "initial_balance": -1},
        {"name": "Alice", "initial_balance": 10.5},
        {"name": "Alice", "initial_balance": "100"},
    ],
)
def test_create_account_rejects_invalid_payload(client, payload):
    response = client.post("/accounts", json=payload)

    assert response.status_code == 422


def test_get_account(client, create_account):
    account = create_account("Alice", 250)

    response = client.get(f"/accounts/{account['id']}")

    assert response.status_code == 200
    assert response.json() == account


def test_get_missing_account_returns_404(client):
    response = client.get("/accounts/9999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


@pytest.mark.parametrize("account_id", ["0", "-1", "abc"])
def test_get_account_rejects_invalid_id(client, account_id):
    response = client.get(f"/accounts/{account_id}")

    assert response.status_code == 422
