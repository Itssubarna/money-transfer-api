"""Concurrency tests: many transfers hitting the same accounts at once.

Each worker thread uses its own TestClient (and therefore its own DB
session/connection), and a barrier releases them together to maximise
contention. The invariants checked are the ones the assignment cares
about: no negative balances, no lost money, no 5xx errors.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from app.main import app


def run_concurrently(requests: list[dict]) -> list:
    barrier = Barrier(len(requests))

    def worker(request: dict):
        with TestClient(app) as client:
            barrier.wait()
            return client.post(
                "/transfers",
                json=request["json"],
                headers=request.get("headers", {}),
            )

    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        return list(pool.map(worker, requests))


def transfer_request(from_id, to_id, amount, key=None) -> dict:
    request = {
        "json": {"from_account_id": from_id, "to_account_id": to_id, "amount": amount}
    }
    if key is not None:
        request["headers"] = {"Idempotency-Key": key}
    return request


def history_ids(client, account_id) -> list[int]:
    response = client.get(
        f"/accounts/{account_id}/transactions", params={"limit": 100}
    )
    return [item["id"] for item in response.json()["items"]]


def test_concurrent_overdraft_attempts(client, create_account, get_balance):
    """20 transfers of 10 from a balance of 100: exactly 10 may succeed."""
    sender = create_account("Sender", 100)
    receiver = create_account("Receiver", 0)

    responses = run_concurrently(
        [transfer_request(sender["id"], receiver["id"], 10) for _ in range(20)]
    )

    statuses = sorted(r.status_code for r in responses)
    succeeded = statuses.count(201)
    assert set(statuses) <= {201, 400}, f"unexpected statuses: {statuses}"
    assert succeeded == 10
    assert get_balance(sender["id"]) == 0
    assert get_balance(receiver["id"]) == 100
    assert len(history_ids(client, sender["id"])) == succeeded


def test_concurrent_transfers_conserve_money(client, create_account, get_balance):
    """Opposite-direction transfers (A->B and B->A) must neither deadlock,
    error, nor create/destroy money."""
    a = create_account("A", 1000)
    b = create_account("B", 1000)

    requests = [transfer_request(a["id"], b["id"], 7) for _ in range(10)] + [
        transfer_request(b["id"], a["id"], 3) for _ in range(10)
    ]
    responses = run_concurrently(requests)

    assert [r.status_code for r in responses] == [201] * 20
    assert get_balance(a["id"]) == 1000 - 70 + 30
    assert get_balance(b["id"]) == 1000 + 70 - 30
    assert get_balance(a["id"]) + get_balance(b["id"]) == 2000


def test_concurrent_requests_with_same_idempotency_key(
    client, create_account, get_balance
):
    """Retries racing each other must produce exactly one transfer."""
    sender = create_account("Sender", 1000)
    receiver = create_account("Receiver", 0)

    responses = run_concurrently(
        [
            transfer_request(sender["id"], receiver["id"], 100, key="same-key")
            for _ in range(10)
        ]
    )

    statuses = [r.status_code for r in responses]
    assert set(statuses) <= {200, 201}, f"unexpected statuses: {statuses}"
    assert statuses.count(201) == 1
    assert len({r.json()["id"] for r in responses}) == 1
    assert get_balance(sender["id"]) == 900
    assert get_balance(receiver["id"]) == 100
