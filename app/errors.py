"""Domain errors raised by the service layer.

They carry a stable machine-readable ``code`` and a human ``message`` but
know nothing about HTTP; ``app.error_handlers`` maps them to status codes.
"""


class AppError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class NotFoundError(AppError):
    """A referenced resource does not exist."""


class BusinessRuleError(AppError):
    """The request is well-formed but breaks a business rule."""


class ConflictError(AppError):
    """The request conflicts with existing state."""


class InvalidRequestError(AppError):
    """The request is malformed in a way schema validation cannot catch."""
