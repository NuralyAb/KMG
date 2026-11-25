"""Сервисы приложения. Модуль просит сервис по типу и не знает, кто и как его собрал."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request


class Container:
    def __init__(self) -> None:
        self._items: dict[type, Any] = {}

    def add[T](self, kind: type[T], item: T) -> T:
        if kind in self._items:
            raise ValueError(f"сервис {kind.__name__} уже собран")
        self._items[kind] = item
        return item

    def get[T](self, kind: type[T]) -> T:
        return self._items[kind]


def provide(kind: type) -> Callable[..., Any]:
    """Annotated[Runs, provide(RunManager)] — сервис из контейнера приложения."""
    def resolve(request: Request) -> Any:
        return request.app.state.container.get(kind)
    return Depends(resolve)
