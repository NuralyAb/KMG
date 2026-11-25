"""Встраивание: публикация курсов."""

from glava.modules.catalog.api import Repository
from glava.modules.publishing.router import router
from glava.modules.publishing.service import Publications
from glava.modules.runs.api import RunManager
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    container.add(Publications, Publications(settings.root, container.get(Repository), container.get(RunManager)))
