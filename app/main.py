from fastapi import FastAPI

from app.error_handlers import register_error_handlers
from app.routers import accounts, transfers

app = FastAPI(
    title="Money Transfer API",
    version="1.0.0",
    description=(
        "Create accounts, transfer money between them and read their "
        "transaction history. Amounts are integers in minor units "
        "(e.g. cents)."
    ),
)

register_error_handlers(app)

app.include_router(accounts.router)
app.include_router(transfers.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
