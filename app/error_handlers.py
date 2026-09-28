"""Turn every error into the same JSON envelope:

    {"error": {"code": "...", "message": "...", "details": [...]?}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import (
    AppError,
    BusinessRuleError,
    ConflictError,
    InvalidRequestError,
    NotFoundError,
)

logger = logging.getLogger(__name__)

STATUS_CODES: dict[type[AppError], int] = {
    NotFoundError: 404,
    BusinessRuleError: 400,
    ConflictError: 409,
    InvalidRequestError: 422,
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list | None = None,
) -> JSONResponse:
    error: dict = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(STATUS_CODES.get(type(exc), 400), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"]),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            jsonable_encoder(details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Unknown routes, wrong methods, etc.
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return error_response(500, "INTERNAL_ERROR", "Internal server error")
