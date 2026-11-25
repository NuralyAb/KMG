"""Встраивание: симуляторы."""

from glava.modules.catalog.api import Repository
from glava.modules.runs.api import RunManager
from glava.modules.simulations.router import router
from glava.modules.simulations.service import Simulations
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:  # noqa: ARG001 — подпись общая для всех модулей
    container.add(Simulations, Simulations(container.get(Repository), container.get(RunManager)))
