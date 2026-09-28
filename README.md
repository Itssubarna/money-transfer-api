# Money Transfer API

Create accounts, transfer money between them, and view transaction history.
Balances stay correct even when many requests arrive at once.

**Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite, Pytest

---

## Run

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head              # create tables
uvicorn app.main:app --reload     # http://localhost:8000
python -m pytest                  # run tests
```

- API docs: http://localhost:8000/docs
- `DATABASE_URL` (default `sqlite:///./money_transfer.db`): database file
- `SQLITE_BUSY_TIMEOUT` (default `15`): seconds a write waits for its turn

---

## API

Amounts are **integers in cents** (`1050` = 10.50).

| Method | Path | Success | Purpose |
|---|---|---|---|
| POST | `/accounts` | 201 | Create account |
| GET | `/accounts/{id}` | 200 | Get account and balance |
| POST | `/transfers` | 201 / 200 | Transfer money (200 = retry of an earlier request) |
| GET | `/accounts/{id}/transactions` | 200 | History, newest first (`limit`, `offset`) |
| GET | `/health` | 200 | Health check |

```bash
curl -X POST localhost:8000/accounts -H "Content-Type: application/json" \
     -d '{"name": "Alice", "initial_balance": 10000}'

curl -X POST localhost:8000/transfers -H "Content-Type: application/json" \
     -H "Idempotency-Key: order-42" \
     -d '{"from_account_id": 1, "to_account_id": 2, "amount": 2500}'
```

---

## Errors

All errors use one format: `{"error": {"code": "...", "message": "..."}}`

| Status | Codes |
|---|---|
| 400 | `INSUFFICIENT_FUNDS`, `SAME_ACCOUNT` |
| 404 | `ACCOUNT_NOT_FOUND`, `SENDER_NOT_FOUND`, `RECEIVER_NOT_FOUND`, `NOT_FOUND` |
| 409 | `IDEMPOTENCY_KEY_REUSED` |
| 422 | `VALIDATION_ERROR`, `INVALID_IDEMPOTENCY_KEY` |
| 500 | `INTERNAL_ERROR` |

---

## How a transfer works

1. Validate the request; reject same-account transfers.
2. Take the database write lock.
3. If the idempotency key was already used, return the original transfer.
4. Check both accounts exist.
5. Subtract from sender only if the balance is enough.
6. Add to receiver and record the transfer.
7. Commit. If any step fails, everything is rolled back.

---

## Why it is safe

- **One transfer at a time:** `BEGIN IMMEDIATE` takes the write lock before reading, so no two transfers see the same old balance.
- **Atomic debit:** `UPDATE ... WHERE balance >= amount` checks and subtracts in one statement.
- **Database rules:** balance ≥ 0, amount > 0, sender ≠ receiver, unique idempotency key.
- **Idempotency:** retrying with the same `Idempotency-Key` and body returns the original transfer (200) and moves no money. Same key with a different body returns 409. Failed requests don't save the key.
- **Integers only:** no floats; `10.5`, `"100"` and `true` are rejected.
- **Tested:** 20 parallel transfers of 10 from a balance of 100 give exactly 10 successes and a final balance of 0.

---

## Why SQLite

- **Simple setup:** just a file, no database server.
- **Enough for this project:** supports transactions, `CHECK`, `UNIQUE` and foreign keys.
- **Easy to control:** one writer at a time makes concurrent transfers simple to reason about.
- **Data is persistent:** stored in the database file, which grows with more transactions.
- **For heavy production use:** switch to PostgreSQL (many users, very high volume).

---

## Project layout

```
app/
  routers/    HTTP requests and responses
  services/   business rules and transactions
  db/         models, queries, connection setup
  schemas/    request/response shapes
  errors.py, error_handlers.py
alembic/      migrations
tests/        unit + integration + concurrency tests
```

Flow: **router → service → crud → database**

---

## Limitations

- One writer at a time, so throughput is capped (a very long wait returns a 500; data is never corrupted).
- One machine only; don't put the file on a network drive.
- Not included: authentication, multiple currencies, history entry for the starting balance.