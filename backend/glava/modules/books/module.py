"""Встраивание: книги."""

from glava.modules.books.router import router
from glava.modules.books.service import BookShelf
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    container.add(BookShelf, BookShelf(settings.root))
