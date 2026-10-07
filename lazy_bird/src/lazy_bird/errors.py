"""Typed application errors and their uniform HTTP representation.

Every error that can reach a client is an ``AppError``. The API turns it into:

    {"error": {"code": "<machine readable>", "message": "<human readable>", "details": {...}}}

with the HTTP status declared by the error class. Unexpected exceptions are logged
with their traceback and answered with a generic ``internal_error`` payload, so a
traceback never reaches the user.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class of every error the API may return to a client."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}

    def payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, resource: str, identifier: Any, *, code: str | None = None) -> None:
        super().__init__(
            f"{resource} '{identifier}' does not exist.",
            code=code or f"{resource.lower().replace(' ', '_')}_not_found",
            details={"resource": resource, "id": identifier},
        )


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InvalidInputError(AppError):
    status_code = 422
    code = "invalid_input"


class InvalidSettingsError(InvalidInputError):
    """Settings rejected by an extension ``*Settings`` model, with one message per field."""

    code = "invalid_settings"

    def __init__(self, fields: dict[str, str], *, message: str | None = None) -> None:
        summary = ", ".join(f"{name}: {error}" for name, error in fields.items())
        super().__init__(message or f"Invalid settings ({summary}).", details={"fields": fields})
        self.fields = fields


class UnavailableError(AppError):
    status_code = 503
    code = "unavailable"


class ExternalServiceError(AppError):
    """A dependency outside lazy_bird (LLM API, Hugging Face, SMTP...) failed."""

    status_code = 502
    code = "external_service_error"


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}
