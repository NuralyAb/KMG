"""Опубликованные курсы для ученика, публикация и просмотр курса автором."""

from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import FileResponse

from glava.modules.catalog.api import Repository
from glava.modules.publishing.course_files import media_type, resolve_course_file
from glava.modules.publishing.schemas import LearnCourse, Publication, PublishRequest
from glava.modules.publishing.service import Publications
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter()
RepositoryDep = Annotated[Repository, provide(Repository)]
PublicationsDep = Annotated[Publications, provide(Publications)]


@router.get("/api/learn/courses")
def list_courses(publications: PublicationsDep) -> Envelope[list[LearnCourse]]:
    return ok(publications.courses())


@router.get("/api/learn/courses/{course_id}")
def get_course(course_id: str, publications: PublicationsDep) -> Envelope[LearnCourse]:
    return ok(publications.course(course_id))


@router.get("/learn/{course_id}/{path:path}")
def get_learn_file(course_id: str, path: str, publications: PublicationsDep) -> FileResponse:
    file = resolve_course_file(publications.folder(course_id), path or "index.html")
    return FileResponse(file, media_type=media_type(file), headers={"Cache-Control": "no-cache"})


@router.get("/api/chapters/{chapter_id}/publication")
def get_publication(chapter_id: str, publications: PublicationsDep) -> Envelope[Publication]:
    return ok(publications.state(chapter_id))


@router.post("/api/chapters/{chapter_id}/publication")
def publish(chapter_id: str, request: PublishRequest, repository: RepositoryDep, publications: PublicationsDep) -> Envelope[Publication]:
    return ok(publications.publish(repository.chapter(chapter_id).id, frozenset(request.accepted)))


@router.delete("/api/chapters/{chapter_id}/publication")
def unpublish(chapter_id: str, repository: RepositoryDep, publications: PublicationsDep) -> Envelope[Publication]:
    publications.unpublish(repository.chapter(chapter_id).id)
    return ok(publications.state(chapter_id))


@router.get("/course/{chapter_id}/{path:path}")
def get_course_file(chapter_id: str, path: str, repository: RepositoryDep) -> FileResponse:
    folder = repository.course_folder(repository.chapter(chapter_id).id)
    file = resolve_course_file(folder, path or "index.html")
    # курс пересобирается на месте: браузер каждый раз сверяет версию по ETag
    return FileResponse(file, media_type=media_type(file), headers={"Cache-Control": "no-cache"})
