import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./money_transfer.db")

# How long (seconds) a write transaction waits for SQLite's write lock
# before giving up with "database is locked".
SQLITE_BUSY_TIMEOUT = float(os.getenv("SQLITE_BUSY_TIMEOUT", "15"))
