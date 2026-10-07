"""Translate every exception into the uniform error payload of ``lazy_bird.errors``."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from lazy_bird.errors import AppError, error_payload


def _status_code_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "http_error"


async def _app_error(_: Request, error: AppError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error.payload())


async def _request_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    fields = {}
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", ()) if part not in ("body", "query", "path"))
        fields[location or "request"] = item.get("msg", "Invalid value")
    return JSONResponse(
        status_code=422,
        content=error_payload("invalid_request", "The request is invalid.", {"fields": fields}),
    )


async def _http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
    message = error.detail if isinstance(error.detail, str) else HTTPStatus(error.status_code).phrase
    return JSONResponse(
        status_code=error.status_code,
        content=error_payload(_status_code_name(error.status_code), message),
        headers=getattr(error, "headers", None),
    )


async def _unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.opt(exception=error).error("Unhandled error on {} {}", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_payload("internal_error", "An unexpected error occurred. Details are in the server logs."),
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _request_validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
