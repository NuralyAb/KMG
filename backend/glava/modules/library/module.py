"""Встраивание: база знаний."""

from glava.modules.library.router import router
from glava.modules.library.service import Library
from glava.modules.runs.api import RunManager
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    container.add(Library, Library(settings.root, container.get(RunManager)))
