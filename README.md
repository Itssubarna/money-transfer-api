# Money Transfer API

An API-only money transfer service: create accounts, move money between
them, and read each account's transaction history. Transfers stay correct
when many requests arrive at once.

**Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, SQLite, Pytest.

## Quick start

### Docker Compose

```bash
docker compose up --build            # API on http://localhost:8000
docker compose --profile test run --rm tests   # run the test suite in a container
```

The container applies migrations on startup (`alembic upgrade head`). The
SQLite file is kept in the `sqlite-data` named volume, so it survives restarts.

### Local

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
python -m pytest
```

Interactive API docs: <http://localhost:8000/docs> (ReDoc at `/redoc`).

### Configuration

| Variable              | Default                        | Purpose                                    |
|-----------------------|--------------------------------|--------------------------------------------|
| `DATABASE_URL`        | `sqlite:///./money_transfer.db`| Database file used by the app and Alembic  |
| `SQLITE_BUSY_TIMEOUT` | `15`                           | Seconds a write waits for the write lock   |

## API

All amounts are **integers in minor units** (e.g. cents: `1050` = 10.50).

| Method | Path                               | Success       | Description                     |
|--------|------------------------------------|---------------|---------------------------------|
| POST   | `/accounts`                        | 201           | Create an account               |
| GET    | `/accounts/{id}`                   | 200           | Get account details and balance |
| POST   | `/transfers`                       | 201 / 200     | Transfer money (200 = replay)   |
| GET    | `/accounts/{id}/transactions`      | 200           | Paginated transaction history   |
| GET    | `/health`                          | 200           | Liveness check                  |

```bash
curl -X POST localhost:8000/accounts -H "Content-Type: application/json" \
     -d '{"name": "Alice", "initial_balance": 10000}'

curl -X POST localhost:8000/transfers -H "Content-Type: application/json" \
     -H "Idempotency-Key: 7f1c2e0a-order-42" \
     -d '{"from_account_id": 1, "to_account_id": 2, "amount": 2500}'

curl "localhost:8000/accounts/1/transactions?limit=20&offset=0"
```

Transaction history items include `direction`: `debit` (money left the
account) or `credit` (money arrived), newest first.

### Errors

Every error, including validation errors and unknown routes, uses the same envelope:

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Insufficient account balance",
    "details": [{"field": "body.amount", "message": "..."}]
  }
}
```

`details` is present only for validation errors.

| Status | Codes                                                          |
|--------|----------------------------------------------------------------|
| 400    | `INSUFFICIENT_FUNDS`, `SAME_ACCOUNT`                           |
| 404    | `ACCOUNT_NOT_FOUND`, `SENDER_NOT_FOUND`, `RECEIVER_NOT_FOUND`, `NOT_FOUND` |
| 409    | `IDEMPOTENCY_KEY_REUSED`                                       |
| 422    | `VALIDATION_ERROR`, `INVALID_IDEMPOTENCY_KEY`                  |
| 500    | `INTERNAL_ERROR` (details are logged, never returned)          |

## Design decisions

### Why SQLite

The brief recommends PostgreSQL. I chose SQLite deliberately:

- **No moving parts.** The database is a file, so the whole system runs with
  `docker compose up` (or plain `uvicorn`) with no database server to provision,
  and each test gets a fresh, isolated database in a temp directory.
- **Its locking model makes correctness easy to reason about.** SQLite allows
  exactly one writer at a time. For a ledger, where the key requirement is
  "never double-spend, never lose money", serialising writes is a simple and
  robust guarantee instead of a limitation to work around.
- **Enough for the scope.** A transfer is a handful of indexed statements
  taking well under a millisecond, so one writer at a time still handles
  hundreds to thousands of transfers per second on one machine.
- **Real constraints.** `CHECK`, `UNIQUE` and (with `PRAGMA foreign_keys=ON`)
  foreign keys are all enforced by the database, not just by the application.

The cost is covered under [Trade-offs](#trade-offs-and-limitations).

### Concurrency: how transfers stay correct on SQLite

**The problem.** A naive transfer reads the balance, checks it in Python and
writes back the new value. Python's `sqlite3` driver does not start a
transaction until the first write, so two requests can both read
`balance = 100`, both decide that 60 is affordable, and both write. The result
is an overdraft, or updates that silently overwrite each other. An early version of this
project had exactly this bug: 20 concurrent transfers of 10 from a balance of
100 *all* succeeded.

**The fix has three layers** ([app/db/session.py](app/db/session.py),
[app/db/crud.py](app/db/crud.py)):

1. **`BEGIN IMMEDIATE` for every write transaction.** The driver's implicit
   transaction handling is switched off and SQLAlchemy's `begin` event issues
   `BEGIN` itself. Code that writes runs inside `write_transaction(session)`,
   which marks the connection so the event issues `BEGIN IMMEDIATE`
   instead. That takes SQLite's single write lock *before* anything is read,
   so the idempotency check, balance check, debit, credit and insert run
   as one uninterrupted unit. A concurrent transfer waits (up to
   `SQLITE_BUSY_TIMEOUT`) for the lock and then sees the committed result.
   It never sees stale data. The lock is on the database file, so this holds across
   threads *and* across multiple worker processes.
2. **Conditional atomic debit.** The debit is a single statement:
   ```sql
   UPDATE accounts SET balance = balance - :amount
   WHERE id = :id AND balance >= :amount
   ```
   If it updates 0 rows, the transfer fails with `INSUFFICIENT_FUNDS`. The
   check and the write can't be separated, which also keeps the logic correct on
   a row-locking database such as PostgreSQL.
3. **Database constraints as the backstop:** `CHECK (balance >= 0)`,
   `CHECK (amount > 0)`, `CHECK (from_account_id <> to_account_id)` and
   `UNIQUE (idempotency_key)`. Even a future bug cannot commit a negative
   balance or a duplicate idempotent transfer.

Other settings: **WAL journal mode**, so reads (`GET` endpoints) are never
blocked by an in-progress transfer and don't block it either; read-only requests use a
plain deferred `BEGIN` so they don't take the write lock.
Any error inside a transfer rolls back the whole transaction.

[tests/test_concurrency.py](tests/test_concurrency.py) checks this with real
parallel requests, each on its own connection, released together by a barrier:

- 20 concurrent transfers of 10 from a balance of 100 → exactly 10 succeed, the
  sender ends at 0, and there are no 5xx responses.
- 20 concurrent transfers in *both* directions between two accounts → all
  succeed and the combined balance is unchanged.
- 10 concurrent retries with the same `Idempotency-Key` → exactly one transfer.

### Idempotency

`POST /transfers` accepts an optional `Idempotency-Key` header (1–255 chars).

- First request with a key → transfer created, **201**.
- Retry with the same key and same body → the original transfer, **200**, and
  no money moves.
- Same key with a *different* body → **409 `IDEMPOTENCY_KEY_REUSED`**. This is a
  client bug, and silently returning the old transfer would hide it.
- A request that *fails* (e.g. insufficient funds) does not store the key, so the
  client can retry after fixing the cause.

The key is stored on the transfer row itself with a `UNIQUE` constraint, so no
extra table is needed. The lookup and insert happen under the write lock, so
racing retries cannot both create a transfer. Keys are global and never
expire; a production system would scope them per client and expire them after
about 24 hours.

### Money representation

Amounts and balances are integers in minor units, never floats. Requests are
validated with `StrictInt`, so `10.5`, `"100"` and `true` are rejected, not
coerced. Values are capped at 10^15 so they stay far within SQLite's 64-bit
integer range. The system is single-currency.

### Schema and indexes

- `accounts(id, name, balance, created_at)` with `CHECK (balance >= 0)`.
- `transfers(id, from_account_id, to_account_id, amount, idempotency_key, created_at)`
  with foreign keys to `accounts`, the checks listed above, and indexes on
  `from_account_id` and `to_account_id` for the history query.
- Transaction history is derived from `transfers`. Each transfer is a debit for
  one account and a credit for the other, so there is one source of truth
  and nothing to keep in sync.

### Pagination

`limit` (1–100, default 20) and `offset` (≥ 0). Results are ordered by
`created_at DESC, id DESC`; the `id` tie-breaker keeps ordering stable,
because SQLite timestamps have one-second resolution. Offset pagination is simple and
fine at this scale; cursor (keyset) pagination would be the next step for very
long histories.

### Architecture

```
app/
  main.py            FastAPI app, router and error-handler registration
  config.py          Settings from environment variables
  error_handlers.py  Maps every error to the JSON error envelope
  errors.py          Domain errors (no HTTP knowledge)
  routers/           HTTP layer: parsing, status codes, response models
  services/          Business logic and transaction boundaries
  schemas/           Pydantic request/response models
  db/
    models.py        SQLAlchemy models and constraints
    crud.py          Data access (queries, atomic balance updates)
    session.py       Engine, SQLite locking setup, sessions
alembic/             Migrations
tests/               Unit and integration tests
```

Routers only call services. Services own the transaction boundaries and raise
domain errors. `crud` is the only layer that builds queries.

## Testing

```bash
python -m pytest
```

| File | Kind | Covers |
|------|------|--------|
| `test_schemas.py` | unit | Request validation rules |
| `test_transfer_service.py` | unit | Transfer logic, rollback on every failure path, idempotency, DB constraint |
| `test_db_session.py` | unit | WAL, foreign keys, `BEGIN IMMEDIATE` for writes |
| `test_accounts_api.py`, `test_transfers_api.py`, `test_transactions_api.py` | integration | Every endpoint, status codes, error envelope, pagination |
| `test_concurrency.py` | integration | Overdraft race, money conservation, concurrent idempotent retries |
| `test_migrations.py` | integration | Migrations produce exactly the models' schema and downgrade cleanly |

Each test runs against a fresh temporary SQLite file built with the app's
own engine factory, so tests exercise the same locking behaviour as production.

## Trade-offs and limitations

- **One writer at a time.** Transfers are serialised across the whole database,
  not per account. That's fine for this scope, but throughput is capped and
  unrelated transfers wait on each other. Under extreme load, requests that
  wait longer than `SQLITE_BUSY_TIMEOUT` fail with a 500 instead of corrupting
  data.
- **Single host.** SQLite is a local file, so the API can scale to more worker
  processes on one machine but not across machines. Don't put the file on a
  network filesystem (NFS/SMB), because its locking is unreliable there.
- **Moving to PostgreSQL** would mean changing `DATABASE_URL` and dropping the
  SQLite-specific `connect`/`begin` hooks, then locking the two account rows with
  `SELECT … FOR UPDATE` in ascending id order (to avoid deadlocks) instead of
  `BEGIN IMMEDIATE`. The conditional debit, constraints and idempotency design
  carry over unchanged.
- **Out of scope:** authentication, multiple currencies, and an audit entry for
  an account's initial balance (it is set directly on creation).
