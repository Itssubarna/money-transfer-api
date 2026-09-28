"""Engine and session setup.

SQLite concurrency model (see README "Concurrency"):

* WAL journal mode, so readers never block the writer and vice versa.
* Python's sqlite3 driver normally delays BEGIN until the first write,
  which lets two transfers both read the same balance before either
  writes. We turn that off and issue BEGIN ourselves.
* Write transactions use BEGIN IMMEDIATE, which takes SQLite's single
  write lock up front. Concurrent transfers therefore run one at a
  time; the others wait up to SQLITE_BUSY_TIMEOUT for the lock.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL, SQLITE_BUSY_TIMEOUT

# Execution option marking a transaction that will write.
_BEGIN_IMMEDIATE = "sqlite_begin_immediate"


def create_db_engine(url: str) -> Engine:
    engine = create_engine(
        url,
        connect_args={
            "check_same_thread": False,
            "timeout": SQLITE_BUSY_TIMEOUT,
        },
    )

    @event.listens_for(engine, "connect")
    def configure_connection(dbapi_connection, _):
        # Disable the driver's implicit BEGIN; the "begin" hook below
        # emits it instead.
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def begin_transaction(connection):
        if connection.get_execution_options().get(_BEGIN_IMMEDIATE):
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.exec_driver_sql("BEGIN")

    return engine


engine = create_db_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def write_transaction(session: Session) -> Iterator[None]:
    """Run the block in a transaction holding SQLite's write lock.

    Commits on success and rolls back on any exception. The session must
    not already be in a transaction.
    """
    with session.begin():
        session.connection(execution_options={_BEGIN_IMMEDIATE: True})
        yield
