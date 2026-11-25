"""Вход автора."""

from typing import Annotated

from fastapi import APIRouter, Request, Response
from pydantic import Field

from glava.modules.access.schemas import Me
from glava.modules.access.service import COOKIE, SESSION_S, Access, token_of
from glava.shared.http.container import provide
from glava.shared.http.dto import Model
from glava.shared.http.envelope import Envelope, ok

router = APIRouter(prefix="/api/auth")
AccessDep = Annotated[Access, provide(Access)]


class LoginRequest(Model):
    password: Annotated[str, Field(min_length=1, max_length=500)]


@router.get("/me")
def get_me(request: Request, access: AccessDep) -> Envelope[Me]:
    return ok(Me(role="admin" if access.is_admin(token_of(request.headers)) else "learner", protected=access.is_protected))


@router.post("/login")
def login(request: LoginRequest, response: Response, access: AccessDep) -> Envelope[Me]:
    token = access.login(request.password)
    # Secure не ставится: сервер отвечает только по http на 127.0.0.1
    response.set_cookie(COOKIE, token, max_age=SESSION_S, httponly=True, samesite="strict", path="/")
    return ok(Me(role="admin", protected=True))


@router.post("/logout")
def logout(request: Request, response: Response, access: AccessDep) -> Envelope[Me]:
    access.logout(token_of(request.headers))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return ok(Me(role="learner" if access.is_protected else "admin", protected=access.is_protected))
