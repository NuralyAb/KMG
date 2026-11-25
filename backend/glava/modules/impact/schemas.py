"""Живой факт: запросы и ответы."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from glava.shared.http.dto import Model


class FactProbe(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


class FactEdit(FactProbe):
    accept: bool = False
    minutes: float = Field(gt=0, le=600)
    reason: str = Field(min_length=1, max_length=300)


class FactChange(Model):
    kind: Literal["changed", "added", "removed"]
    claim_id: str
    node_id: str
    before: str
    after: str
    quote: str
    page_pdf: int | None
    old_numbers: tuple[str, ...]
    new_numbers: tuple[str, ...]
    conflicts: tuple[str, ...]
    is_serious: bool


class FactStep(Model):
    id: str
    title: str
    order: int | None


class FactPlace(Model):
    id: str
    step_id: str
    title: str
    is_certain: bool


class FactReplacement(Model):
    where: str
    before: str
    after: str


class FactReport(Model):
    chapter: str
    changes: tuple[FactChange, ...]
    fields: dict[str, Any]
    steps: tuple[FactStep, ...]
    tasks: tuple[FactPlace, ...]
    pictures: tuple[FactPlace, ...]
    simulations: tuple[FactPlace, ...]
    videos: tuple[FactPlace, ...]
    replaced: tuple[FactReplacement, ...] = ()
    tasks_hidden: tuple[str, ...] = ()
