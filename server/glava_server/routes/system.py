"""Состояние, поиск, расход и файлы курса."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from glava_server.course_files import media_type, resolve_course_file
from glava_server.envelope import Envelope, ok
from glava_server.errors import invalid
from glava_server.metrics import totals
from glava_server.schemas import FoundClaim, Health, MetricRow
from glava_server.search import MIN_QUERY, normalized, search_claims
from glava_server.services import ServicesDep
from glava_server.system import health

router = APIRouter()


@router.get("/api/health")
def get_health(services: ServicesDep) -> Envelope[Health]:
    return ok(health(services.models.env()))


@router.get("/api/search")
def search(
    services: ServicesDep, q: Annotated[str, Query(max_length=200)], chapter: str = "", page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[list[FoundClaim]]:
    if len(normalized(q)) < MIN_QUERY:
        raise invalid(f"Запрос для поиска — от {MIN_QUERY} знаков")
    chapters = [services.repository.chapter(chapter)] if chapter else services.repository.chapters()
    found = search_claims(services.repository, chapters, q)
    return ok(found[(page - 1) * limit:page * limit], {"total": len(found), "page": page, "limit": limit})


@router.get("/api/metrics")
def get_metrics(services: ServicesDep) -> Envelope[list[MetricRow]]:
    rows = services.repository.metrics()
    return ok(rows, asdict(totals(rows)))


@router.get("/course/{chapter_id}/{path:path}")
def get_course_file(chapter_id: str, path: str, services: ServicesDep) -> FileResponse:
    folder = services.repository.course_folder(services.repository.chapter(chapter_id).id)
    file = resolve_course_file(folder, path or "index.html")
    # курс пересобирается на месте: браузер каждый раз сверяет версию по ETag
    return FileResponse(file, media_type=media_type(file), headers={"Cache-Control": "no-cache"})
