"""Общие объекты приложения и доступ к ним из маршрутов."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from glava_server.config import Settings
from glava_server.repository import Repository
from glava_server.runs.manager import RunManager


@dataclass(frozen=True)
class Services:
    settings: Settings
    repository: Repository
    runs: RunManager


def build_services(settings: Settings) -> Services:
    return Services(settings, Repository(settings.root), RunManager(settings.root, settings.run_command, settings.max_processes))


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]
