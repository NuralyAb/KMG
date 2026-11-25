"""Встраивание: запуски."""

from glava.modules.llm.api import ModelStore
from glava.modules.runs.manager import RunManager
from glava.modules.runs.router import router
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    models = container.get(ModelStore)
    container.add(RunManager, RunManager(settings.root, settings.run_command, settings.max_processes, models.env))
