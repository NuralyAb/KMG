"""Главы, узлы и данные этапов, поиск и расход."""

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from glava.modules.catalog import views as view
from glava.modules.catalog.ports import ChapterStatus
from glava.modules.catalog.repository import Repository
from glava.modules.catalog.schemas import (
    ChapterCard,
    ChapterDetail,
    FoundClaim,
    NodeDetail,
    TaskType,
    Trust,
    Video,
)
from glava.modules.catalog.search import MIN_QUERY, normalized, search_claims
from glava.modules.metrics.api import MetricRow, totals
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok
from glava.shared.http.errors import invalid

router = APIRouter()
StatusDep = Annotated[ChapterStatus, provide(ChapterStatus)]
RepositoryDep = Annotated[Repository, provide(Repository)]
Rows = Envelope[list[dict[str, Any]]]


@router.get("/api/chapters")
def list_chapters(repository: RepositoryDep, status: StatusDep) -> Envelope[list[ChapterCard]]:
    metrics, active = repository.metrics(), status.active_runs()
    cards = [view.build_card(repository, c, metrics, active.get(c.id)) for c in repository.chapters()]
    return ok([c.model_copy(update={"published_at": status.published_at(c.id)}) for c in cards])


@router.get("/api/chapters/{chapter_id}")
def get_chapter(chapter_id: str, repository: RepositoryDep, status: StatusDep) -> Envelope[ChapterDetail]:
    chapter = repository.chapter(chapter_id)
    found = view.build_detail(repository, chapter, repository.metrics(), status.active_runs().get(chapter.id))
    return ok(found.model_copy(update={"published_at": status.published_at(chapter.id)}))


@router.get("/api/chapters/{chapter_id}/nodes/{node_id}")
def get_node(chapter_id: str, node_id: str, repository: RepositoryDep) -> Envelope[NodeDetail]:
    return ok(view.build_node(repository, repository.chapter(chapter_id).id, node_id))


@router.get("/api/chapters/{chapter_id}/coverage")
def get_coverage(chapter_id: str, repository: RepositoryDep, uncovered: Annotated[int, Query(ge=0, le=1)] = 0) -> Rows:
    found = repository.coverage(repository.chapter(chapter_id).id)
    return ok([r for r in found if not uncovered or not view.is_covered(r)], view.coverage_meta(found))


@router.get("/api/chapters/{chapter_id}/errata")
def get_errata(chapter_id: str, repository: RepositoryDep) -> Rows:
    found = repository.errata(chapter_id)
    return ok(found, view.errata_meta(found))


@router.get("/api/chapters/{chapter_id}/trust")
def get_trust(chapter_id: str, repository: RepositoryDep) -> Envelope[Trust]:
    return ok(repository.trust(repository.chapter(chapter_id).id))


@router.get("/api/chapters/{chapter_id}/routing")
def get_routing(chapter_id: str, repository: RepositoryDep) -> Rows:
    return ok(repository.routes(repository.chapter(chapter_id).id))


@router.get("/api/chapters/{chapter_id}/tasks")
def get_tasks(chapter_id: str, repository: RepositoryDep, kind: Annotated[TaskType | Literal[""], Query(alias="type")] = "", node: str = "") -> Rows:
    tasks = repository.tasks(repository.chapter(chapter_id).id)
    return ok(*view.filter_tasks(tasks, kind, node))


@router.get("/api/chapters/{chapter_id}/illustrations")
def get_illustrations(chapter_id: str, repository: RepositoryDep) -> Rows:
    return ok(view.illustrations_with_url(repository, repository.chapter(chapter_id).id))


@router.get("/api/chapters/{chapter_id}/videos")
def get_videos(chapter_id: str, repository: RepositoryDep) -> Envelope[list[Video]]:
    return ok(view.build_videos(repository, repository.chapter(chapter_id).id))


@router.get("/api/search")
def search(
    repository: RepositoryDep, q: Annotated[str, Query(max_length=200)], chapter: str = "", page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[list[FoundClaim]]:
    if len(normalized(q)) < MIN_QUERY:
        raise invalid(f"Запрос для поиска — от {MIN_QUERY} знаков")
    chapters = [repository.chapter(chapter)] if chapter else repository.chapters()
    found = search_claims(repository, chapters, q)
    return ok(found[(page - 1) * limit:page * limit], {"total": len(found), "page": page, "limit": limit})


@router.get("/api/metrics")
def get_metrics(repository: RepositoryDep) -> Envelope[list[MetricRow]]:
    rows = repository.metrics()
    return ok(rows, asdict(totals(rows)))
