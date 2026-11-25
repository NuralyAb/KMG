"""Публичный вход модуля: сверка текста со сканом. Другие модули импортируют только отсюда."""

from glava.modules.errata.scan_check import (
    for_pages,
    make_errata,
    not_caught,
    number_sources,
    prompt_block,
    render_page,
    suspects_in,
)

__all__ = [
    "for_pages",
    "make_errata",
    "not_caught",
    "number_sources",
    "prompt_block",
    "render_page",
    "suspects_in",
]
