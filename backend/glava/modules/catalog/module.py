"""Встраивание: главы."""

from glava.modules.catalog.repository import Repository
from glava.modules.catalog.router import router
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    container.add(Repository, Repository(settings.root))
