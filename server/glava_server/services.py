"""Общие объекты приложения и доступ к ним из маршрутов."""

import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from glava_server.access import Access
from glava_server.config import Settings
from glava_server.library import Library
from glava_server.model_settings import ModelStore
from glava_server.publications import Publications
from glava_server.repository import Repository
from glava_server.runs.manager import RunManager


@dataclass(frozen=True)
class Services:
    settings: Settings
    repository: Repository
    runs: RunManager
    library: Library
    models: ModelStore
    publications: Publications
    access: Access


def build_services(settings: Settings) -> Services:
    models = ModelStore(settings.root, os.environ)
    runs = RunManager(settings.root, settings.run_command, settings.max_processes, models.env)
    repository = Repository(settings.root)
    return Services(settings, repository, runs, Library(settings.root, runs), models, Publications(settings.root, repository, runs),
                    Access(settings.admin_password))


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]
