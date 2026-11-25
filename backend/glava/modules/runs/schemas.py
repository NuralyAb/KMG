"""Запуски конвейера: запросы и ответы."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from glava.shared.http.dto import Model

RunCommand = Literal["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "review", "video", "simulation", "extract", "audit", "verify", "fact"]
RunState = Literal["queued", "running", "done", "failed", "cancelled"]


class Run(Model):
    id: str
    command: RunCommand
    chapter: str
    args: dict[str, Any]
    state: RunState
    started_at: str | None
    finished_at: str | None
    exit_code: int | None
    log_tail: list[str]


class RunRequest(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command: Literal["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "video", "simulation", "audit", "verify"]
    mutants: bool | None = None
    chapter: str = Field(min_length=1, max_length=200)
    limit: int | None = Field(default=None, ge=1, le=1000)
    node: str | None = Field(default=None, max_length=200)
    format: Literal["short", "wide"] | None = None
    template: str | None = Field(default=None, max_length=200)
    until: Literal["design"] | None = None
