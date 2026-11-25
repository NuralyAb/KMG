"""Публичный вход модуля: рисунки со скана. Другие модули импортируют только отсюда."""

from glava.modules.figure_reading.reading import (
    FigurePage,
    figure_errata,
    figure_pages,
    page_key,
    read_figures,
    with_readings,
)

__all__ = [
    "FigurePage",
    "figure_errata",
    "figure_pages",
    "page_key",
    "read_figures",
    "with_readings",
]
