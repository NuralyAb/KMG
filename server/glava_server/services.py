"""Общие объекты приложения и доступ к ним из маршрутов."""

import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from glava_server.config import Settings
from glava_server.library import Library
from glava_server.model_settings import ModelStore
from glava_server.repository import Repository
from glava_server.runs.manager import RunManager


@dataclass(frozen=True)
class Services:
    settings: Settings
    repository: Repository
    runs: RunManager
    library: Library
    models: ModelStore


def build_services(settings: Settings) -> Services:
    models = ModelStore(settings.root, os.environ)
    runs = RunManager(settings.root, settings.run_command, settings.max_processes, models.env)
    return Services(settings, Repository(settings.root), runs, Library(settings.root, runs), models)


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]
