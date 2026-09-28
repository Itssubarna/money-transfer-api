from fastapi import FastAPI

from app.routers import accounts, transfers

app = FastAPI(
    title="Money Transfer API",
    version="1.0.0",
)

app.include_router(accounts.router)
app.include_router(transfers.router)