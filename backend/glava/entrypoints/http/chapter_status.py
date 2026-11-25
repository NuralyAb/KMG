"""Связка модулей: что модулю глав известно о запусках и публикациях."""

from collections.abc import Mapping

from glava.modules.publishing.api import Publications
from glava.modules.runs.api import RunManager


class LiveChapterStatus:
    def __init__(self, runs: RunManager, publications: Publications) -> None:
        self._runs = runs
        self._publications = publications

    def active_runs(self) -> Mapping[str, str]:
        return self._runs.active_by_chapter()

    def published_at(self, chapter_id: str) -> str | None:
        return self._publications.published_at(chapter_id)
