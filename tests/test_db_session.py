"""The SQLite settings the concurrency guarantees depend on."""

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.db import write_transaction


def capture_sql(engine) -> list[str]:
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(_conn, _cursor, statement, *_):
        statements.append(statement)

    return statements


def test_connection_pragmas(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_write_transaction_takes_write_lock_up_front(engine):
    statements = capture_sql(engine)

    with Session(engine) as session, write_transaction(session):
        session.execute(text("SELECT 1"))

    assert statements[0] == "BEGIN IMMEDIATE"


def test_read_transaction_uses_plain_begin(engine):
    statements = capture_sql(engine)

    with Session(engine) as session:
        session.execute(text("SELECT 1"))

    assert statements[0] == "BEGIN"
