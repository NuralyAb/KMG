"""Встраивание: проверка пакета."""

from glava.modules.review.router import router
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    """Своих сервисов нет."""
