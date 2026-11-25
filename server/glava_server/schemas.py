"""Типы ответов и запросов по docs/API.md."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StageName = Literal["errata", "layer", "routing", "tasks", "illustrations", "course"]
StageState = Literal["missing", "ready", "stale"]
RunCommand = Literal["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "review", "video", "simulation"]
RunState = Literal["queued", "running", "done", "failed", "cancelled"]
Severity = Literal["critical", "significant", "minor"]
TaskType = Literal["single", "multiple", "order", "gap", "calc"]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True)


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


class MetricRow(Model):
    chapter: str
    stage: str
    nodes: int
    llm_tokens_in: int
    llm_tokens_out: int
    money_usd: float
    person_minutes: float
    mentor_minutes: float
    video_seconds: float
    manual_share: float


class Health(Model):
    status: Literal["ok"] = "ok"
    provider: str
    model: str
    claude_found: bool
    ffmpeg_found: bool


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

    command: Literal["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "video", "simulation"]
    chapter: str = Field(min_length=1, max_length=200)
    limit: int | None = Field(default=None, ge=1, le=1000)
    node: str | None = Field(default=None, max_length=200)
    format: Literal["short", "wide"] | None = None
    template: str | None = Field(default=None, max_length=200)
    until: Literal["design"] | None = None


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
