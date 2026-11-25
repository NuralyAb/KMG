"""Что модулю глав нужно знать от других модулей. Реализацию подставляет сборка приложения."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class ChapterStatus(Protocol):
    def active_runs(self) -> Mapping[str, str]:
        """Глава → идущий запуск."""

    def published_at(self, chapter_id: str) -> str | None:
        """Когда курс главы опубликован."""
