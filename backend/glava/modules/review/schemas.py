"""Проверка чужого пакета: ответы."""

from typing import Literal

from glava.shared.http.dto import Model

Severity = Literal["critical", "significant", "minor"]


class Remark(Model):
    target: str
    category: str
    severity: Severity
    problem: str
    fix: str
    page_pdf: int | None = None
    quote: str | None = None


class Review(Model):
    package_id: str
    chapter: str | None
    created_at: str
    remarks: tuple[Remark, ...]
    counts: dict[Severity, int]
