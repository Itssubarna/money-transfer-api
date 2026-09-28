"""Integration tests for GET /accounts/{id}/transactions."""

import pytest


def transfer(client, from_id, to_id, amount):
    response = client.post(
        "/transfers",
        json={"from_account_id": from_id, "to_account_id": to_id, "amount": amount},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_history(client, create_account):
    a = create_account("Alice", 100)

    response = client.get(f"/accounts/{a['id']}/transactions")

    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 20, "offset": 0}


def test_history_shows_direction_newest_first(client, create_account):
    a = create_account("Alice", 1000)
    b = create_account("Bob", 1000)
    t1 = transfer(client, a["id"], b["id"], 100)
    t2 = transfer(client, b["id"], a["id"], 40)

    items = client.get(f"/accounts/{a['id']}/transactions").json()["items"]

    assert [(i["id"], i["direction"]) for i in items] == [
        (t2["id"], "credit"),
        (t1["id"], "debit"),
    ]


def test_history_excludes_unrelated_transfers(client, create_account):
    a = create_account("Alice", 1000)
    b = create_account("Bob", 1000)
    c = create_account("Carol", 0)
    transfer(client, b["id"], c["id"], 10)

    items = client.get(f"/accounts/{a['id']}/transactions").json()["items"]

    assert items == []


def test_pagination(client, create_account):
    a = create_account("Alice", 1000)
    b = create_account("Bob", 0)
    ids = [transfer(client, a["id"], b["id"], 1)["id"] for _ in range(5)]
    newest_first = list(reversed(ids))

    def page(limit, offset):
        response = client.get(
            f"/accounts/{a['id']}/transactions",
            params={"limit": limit, "offset": offset},
        )
        assert response.status_code == 200
        return [item["id"] for item in response.json()["items"]]

    assert page(2, 0) == newest_first[0:2]
    assert page(2, 2) == newest_first[2:4]
    assert page(2, 4) == newest_first[4:5]
    assert page(2, 6) == []


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}]
)
def test_invalid_pagination_params(client, create_account, params):
    a = create_account("Alice", 0)

    response = client.get(f"/accounts/{a['id']}/transactions", params=params)

    assert response.status_code == 422


def test_history_for_missing_account_returns_404(client):
    response = client.get("/accounts/9999/transactions")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
