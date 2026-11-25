"""Встраивание: выбор модели."""

import os

from glava.modules.llm.router import router
from glava.modules.llm.settings import ModelStore
from glava.shared.http.container import Container
from glava.shared.http.settings import Settings

__all__ = ["router", "install"]


def install(container: Container, settings: Settings) -> None:
    container.add(ModelStore, ModelStore(settings.root, os.environ))
