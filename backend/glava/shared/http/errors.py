"""Ошибки API: код и понятный текст по-русски, без внутренних подробностей."""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from glava.shared.http.envelope import failure

log = logging.getLogger("glava.http")
HTTP_TEXTS: dict[int, tuple[int, str, str]] = {
    404: (404, "not_found", "Такого адреса нет"),
    405: (400, "bad_request", "Этот адрес не принимает такой запрос"),
    413: (413, "too_large", "Запрос слишком большой"),
    422: (422, "invalid", "Запрос заполнен неверно"),
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", what)


def conflict(message: str) -> ApiError:
    return ApiError(409, "conflict", message)


def invalid(message: str) -> ApiError:
    return ApiError(422, "invalid", message)


def error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(failure(error.code, error.message), status_code=error.status)


def _field(errors: Sequence[Any]) -> str:
    parts = [str(p) for p in (errors[0].get("loc") or ()) if p not in ("body", "query", "path")] if errors else []
    return ".".join(parts)


def _validation_message(errors: Sequence[Any]) -> str:
    if errors and errors[0].get("type") == "json_invalid":
        return "Тело запроса — не JSON"
    name = _field(errors)
    return f"Проверьте поле «{name}»: значение отсутствует или не подходит" if name else "Запрос заполнен неверно"


async def _on_api_error(_: Request, error: ApiError) -> JSONResponse:
    return error_response(error)


async def _on_http_error(_: Request, error: HTTPException) -> JSONResponse:
    status, code, message = HTTP_TEXTS.get(error.status_code, (400, "bad_request", "Запрос не удалось разобрать"))
    return error_response(ApiError(status, code, message))


async def _on_invalid(_: Request, error: RequestValidationError) -> JSONResponse:
    return error_response(invalid(_validation_message(error.errors())))


async def _on_unexpected(request: Request, error: Exception) -> JSONResponse:
    log.error("сбой на %s %s: %s", request.method, request.url.path, type(error).__name__)
    return error_response(ApiError(500, "internal", "Внутренняя ошибка сервера, подробности в его журнале"))


def install_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _on_api_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _on_http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _on_invalid)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _on_unexpected)
