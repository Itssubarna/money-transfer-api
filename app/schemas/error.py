from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*status_codes: int) -> dict:
    """OpenAPI ``responses=`` entries documenting the error envelope."""
    descriptions = {
        400: "Business rule violated (e.g. insufficient funds)",
        404: "Resource not found",
        409: "Conflict with existing state",
        422: "Request validation failed",
    }
    return {
        code: {"model": ErrorResponse, "description": descriptions[code]}
        for code in status_codes
    }
