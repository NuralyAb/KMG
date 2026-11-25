"""Единый конверт ответа."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    code: str
    message: str


class Envelope[T](BaseModel):
    model_config = ConfigDict(frozen=True)

    success: bool = True
    data: T
    error: ErrorBody | None = None
    meta: dict[str, Any] | None = None


def ok[T](data: T, meta: dict[str, Any] | None = None) -> Envelope[T]:
    return Envelope(data=data, meta=meta)


def failure(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "data": None, "error": {"code": code, "message": message}, "meta": None}
