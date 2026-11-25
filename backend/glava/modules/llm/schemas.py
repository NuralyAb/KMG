"""Выбор модели: запросы и ответы."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from glava.shared.http.dto import Model

Provider = Literal["claude_code", "anthropic", "openai", "local"]


class ModelChoice(Model):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    provider: Provider
    model: str | None = Field(default=None, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$")
    base_url: str | None = Field(default=None, max_length=300)
    price_in: float | None = Field(default=None, ge=0, le=10_000, allow_inf_nan=False)
    price_out: float | None = Field(default=None, ge=0, le=10_000, allow_inf_nan=False)
    budget_usd: float | None = Field(default=None, gt=0, le=1000, allow_inf_nan=False)
    context: int | None = Field(default=None, ge=1024, le=10_000_000)

    @field_validator("base_url")
    @classmethod
    def _plain_address(cls, value: str | None) -> str | None:
        if not value:
            return None
        parts = urlsplit(value)
        _ = parts.port  # неверный порт — ValueError
        has_secret = "@" in parts.netloc or parts.query or parts.fragment
        if parts.scheme not in ("http", "https") or not parts.hostname or has_secret or not value.isprintable():
            raise ValueError("нужен адрес вида http://127.0.0.1:11434/v1")
        return value

    @model_validator(mode="after")
    def _complete(self) -> "ModelChoice":
        if self.provider in ("openai", "local") and not self.model:
            raise ValueError("укажите имя модели")
        if self.provider == "local" and self.context is None:
            raise ValueError("укажите контекст модели: иначе обрезка главы останется незамеченной")
        if self.provider == "openai" and not (self.price_in and self.price_out):
            raise ValueError("укажите цены: без них не работает потолок расхода")
        return self


class ModelSettings(Model):
    provider: str
    model: str | None = None
    base_url: str | None = None
    price_in: float | None = None
    price_out: float | None = None
    budget_usd: float | None = None
    context: int | None = None
    origin: Literal["file", "env"]
    keys: dict[str, bool]
