"""Встраивание: живой факт."""

from glava.modules.catalog.api import Repository
from glava.modules.impact.router import router
from glava.modules.impact.service import Facts
from glava.modules.runs.api import RunManager
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:  # noqa: ARG001 — подпись общая для всех модулей
    container.add(Facts, Facts(container.get(Repository), container.get(RunManager)))
