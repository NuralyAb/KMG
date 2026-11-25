"""Публикация курса: запросы и ответы."""

from typing import Annotated

from pydantic import ConfigDict, Field

from glava.shared.http.dto import Model


class CourseStep(Model):
    id: str
    order: int
    title: str
    minutes: int


class CoursePart(Model):
    title: str
    steps: tuple[CourseStep, ...]


class LearnCourse(Model):
    id: str
    title: str
    book: str
    steps: int
    minutes: int
    tasks: int
    parts: tuple[CoursePart, ...]
    published_at: str


class PublishCheck(Model):
    code: str
    text: str


class Publication(Model):
    published_at: str | None
    is_current: bool
    problem: str | None
    checks: tuple[PublishCheck, ...]
    accepted: tuple[str, ...]


class PublishRequest(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted: tuple[Annotated[str, Field(max_length=100)], ...] = Field(default=(), max_length=50)
