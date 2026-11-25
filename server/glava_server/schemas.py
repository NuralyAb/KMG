"""Типы ответов и запросов по docs/API.md."""

from typing import Annotated, Any, Literal

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

StageName = Literal["errata", "layer", "routing", "tasks", "illustrations", "course"]
StageState = Literal["missing", "ready", "stale"]
RunCommand = Literal["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "review", "video", "extract", "audit", "verify"]
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

    command: Literal["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "video", "audit", "verify"]
    mutants: bool | None = None
    chapter: str = Field(min_length=1, max_length=200)
    limit: int | None = Field(default=None, ge=1, le=1000)
    node: str | None = Field(default=None, max_length=200)
    format: Literal["short", "wide"] | None = None
    template: str | None = Field(default=None, max_length=200)


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


PageState = Literal["text", "doubtful", "scan", "empty"]
Provider = Literal["claude_code", "anthropic", "openai", "local"]


class LibraryPage(Model):
    page: int
    state: PageState
    method: str
    chars: int
    reasons: tuple[str, ...] = ()


class Source(Model):
    id: str
    name: str
    kind: str
    bytes: int
    added_at: str
    state: Literal["uploaded", "extracting", "ready", "failed"]
    run: str | None
    pages: int
    counts: dict[PageState, int]
    chapters: tuple[str, ...]


class SourceDetail(Source):
    page_list: tuple[LibraryPage, ...]


class ExtractRequest(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    vision: bool = False


class NewChapter(Model):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    book: str | None = Field(default=None, max_length=300)
    pages: tuple[tuple[Annotated[int, Field(ge=1, le=100_000)], Annotated[int, Field(ge=1, le=100_000)]], ...] = Field(min_length=1, max_length=20)
    domain: str = Field(min_length=1, max_length=100)


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


class Trust(Model):
    audit: dict[str, Any] | None
    audit_stale: bool
    verify: dict[str, Any] | None
    verify_stale: bool


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


class Me(Model):
    role: Literal["admin", "learner"]
    protected: bool
