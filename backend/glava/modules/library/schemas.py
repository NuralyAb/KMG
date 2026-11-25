"""База знаний: запросы и ответы."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from glava.shared.http.dto import Model

PageState = Literal["text", "doubtful", "scan", "empty"]


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
