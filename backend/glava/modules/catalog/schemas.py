"""Главы, узлы и данные этапов: ответы."""

from typing import Any, Literal

from glava.shared.http.dto import Model

StageName = Literal["errata", "layer", "routing", "tasks", "illustrations", "course"]
StageState = Literal["missing", "ready", "stale"]
TaskType = Literal["single", "multiple", "order", "gap", "calc"]


class Stage(Model):
    name: StageName
    state: StageState
    updated_at: str | None


class Counts(Model):
    nodes: int
    claims: int
    tasks: int
    illustrations: int
    errata: int
    units: int
    units_covered: int
    videos: int


class ChapterCard(Model):
    id: str
    title: str
    book: str
    domain: str
    pages: tuple[int, ...]
    counts: Counts
    issues: int
    stages: tuple[Stage, ...]
    cost_usd: float
    tokens_in: int
    tokens_out: int
    course_url: str | None
    active_run: str | None
    published_at: str | None = None


class Difficulty(Model):
    primary: str
    secondary: str | None


class NodeRow(Model):
    id: str
    order: int
    title: str
    short_title: str
    difficulty: Difficulty
    threshold: bool
    pages: tuple[int, ...]
    claims: int
    tasks: int
    format: str | None
    needs_scan: int


class Part(Model):
    title: str
    nodes: tuple[NodeRow, ...]


class ChapterDetail(ChapterCard):
    parts: tuple[Part, ...]


class NodeDetail(Model):
    node: dict[str, Any]
    route: dict[str, Any] | None
    tasks: list[dict[str, Any]]
    illustrations: list[dict[str, Any]]
    prev: str | None
    next: str | None


class Video(Model):
    id: str
    chapter: str
    title: str
    format: Literal["9:16", "16:9"]
    duration_s: float
    url: str
    subtitles_url: str | None
    passport: dict[str, Any]
    problems: list[str]


class FoundClaim(Model):
    chapter: str
    node_id: str
    node_title: str
    claim_id: str
    text: str
    quote: str
    page_pdf: int | None


class Trust(Model):
    audit: dict[str, Any] | None
    audit_stale: bool
    verify: dict[str, Any] | None
    verify_stale: bool
