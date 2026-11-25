"""Главы, узлы и данные этапов."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from glava_server import chapters as view
from glava_server.envelope import Envelope, ok
from glava_server.schemas import ChapterCard, ChapterDetail, NodeDetail, TaskType, Trust, Video
from glava_server.services import ServicesDep

router = APIRouter(prefix="/api/chapters")
Rows = Envelope[list[dict[str, Any]]]


@router.get("")
def list_chapters(services: ServicesDep) -> Envelope[list[ChapterCard]]:
    repository, metrics, active = services.repository, services.repository.metrics(), services.runs.active_by_chapter()
    return ok([view.build_card(repository, c, metrics, active.get(c.id)) for c in repository.chapters()])


@router.get("/{chapter_id}")
def get_chapter(chapter_id: str, services: ServicesDep) -> Envelope[ChapterDetail]:
    repository = services.repository
    chapter = repository.chapter(chapter_id)
    return ok(view.build_detail(repository, chapter, repository.metrics(), services.runs.active_by_chapter().get(chapter.id)))


@router.get("/{chapter_id}/nodes/{node_id}")
def get_node(chapter_id: str, node_id: str, services: ServicesDep) -> Envelope[NodeDetail]:
    return ok(view.build_node(services.repository, services.repository.chapter(chapter_id).id, node_id))


@router.get("/{chapter_id}/coverage")
def get_coverage(chapter_id: str, services: ServicesDep, uncovered: Annotated[int, Query(ge=0, le=1)] = 0) -> Rows:
    found = services.repository.coverage(services.repository.chapter(chapter_id).id)
    return ok([r for r in found if not uncovered or not view.is_covered(r)], view.coverage_meta(found))


@router.get("/{chapter_id}/errata")
def get_errata(chapter_id: str, services: ServicesDep) -> Rows:
    found = services.repository.errata(chapter_id)
    return ok(found, view.errata_meta(found))


@router.get("/{chapter_id}/trust")
def get_trust(chapter_id: str, services: ServicesDep) -> Envelope[Trust]:
    return ok(services.repository.trust(services.repository.chapter(chapter_id).id))


@router.get("/{chapter_id}/routing")
def get_routing(chapter_id: str, services: ServicesDep) -> Rows:
    return ok(services.repository.routes(services.repository.chapter(chapter_id).id))


@router.get("/{chapter_id}/tasks")
def get_tasks(chapter_id: str, services: ServicesDep, kind: Annotated[TaskType | Literal[""], Query(alias="type")] = "", node: str = "") -> Rows:
    tasks = services.repository.tasks(services.repository.chapter(chapter_id).id)
    return ok(*view.filter_tasks(tasks, kind, node))


@router.get("/{chapter_id}/illustrations")
def get_illustrations(chapter_id: str, services: ServicesDep) -> Rows:
    return ok(view.illustrations_with_url(services.repository, services.repository.chapter(chapter_id).id))


@router.get("/{chapter_id}/videos")
def get_videos(chapter_id: str, services: ServicesDep) -> Envelope[list[Video]]:
    return ok(view.build_videos(services.repository, services.repository.chapter(chapter_id).id))
