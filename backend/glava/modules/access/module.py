"""Встраивание: вход автора."""

from glava.modules.access.router import router
from glava.modules.access.service import Access
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    container.add(Access, Access(settings.admin_password))
