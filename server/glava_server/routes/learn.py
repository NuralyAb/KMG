"""Экран ученика: опубликованные курсы. И вход автора."""

from typing import Annotated

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from pydantic import Field

from glava_server.access import COOKIE, SESSION_S, token_of
from glava_server.course_files import media_type, resolve_course_file
from glava_server.envelope import Envelope, ok
from glava_server.schemas import LearnCourse, Me, Model, Publication, PublishRequest
from glava_server.services import ServicesDep

router = APIRouter()


class LoginRequest(Model):
    password: Annotated[str, Field(min_length=1, max_length=500)]


@router.get("/api/learn/courses")
def list_courses(services: ServicesDep) -> Envelope[list[LearnCourse]]:
    return ok(services.publications.courses())


@router.get("/api/learn/courses/{course_id}")
def get_course(course_id: str, services: ServicesDep) -> Envelope[LearnCourse]:
    return ok(services.publications.course(course_id))


@router.get("/learn/{course_id}/{path:path}")
def get_learn_file(course_id: str, path: str, services: ServicesDep) -> FileResponse:
    file = resolve_course_file(services.publications.folder(course_id), path or "index.html")
    return FileResponse(file, media_type=media_type(file), headers={"Cache-Control": "no-cache"})


@router.get("/api/auth/me")
def get_me(request: Request, services: ServicesDep) -> Envelope[Me]:
    return ok(Me(role="admin" if services.access.is_admin(token_of(request.headers)) else "learner", protected=services.access.is_protected))


@router.post("/api/auth/login")
def login(request: LoginRequest, response: Response, services: ServicesDep) -> Envelope[Me]:
    token = services.access.login(request.password)
    # Secure не ставится: сервер отвечает только по http на 127.0.0.1
    response.set_cookie(COOKIE, token, max_age=SESSION_S, httponly=True, samesite="strict", path="/")
    return ok(Me(role="admin", protected=True))


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, services: ServicesDep) -> Envelope[Me]:
    services.access.logout(token_of(request.headers))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return ok(Me(role="learner" if services.access.is_protected else "admin", protected=services.access.is_protected))


@router.get("/api/chapters/{chapter_id}/publication")
def get_publication(chapter_id: str, services: ServicesDep) -> Envelope[Publication]:
    return ok(services.publications.state(chapter_id))


@router.post("/api/chapters/{chapter_id}/publication")
def publish(chapter_id: str, request: PublishRequest, services: ServicesDep) -> Envelope[Publication]:
    return ok(services.publications.publish(services.repository.chapter(chapter_id).id, frozenset(request.accepted)))


@router.delete("/api/chapters/{chapter_id}/publication")
def unpublish(chapter_id: str, services: ServicesDep) -> Envelope[Publication]:
    services.publications.unpublish(services.repository.chapter(chapter_id).id)
    return ok(services.publications.state(chapter_id))
