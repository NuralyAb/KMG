"""Публичный вход модуля: текст главы: страницы, единицы, таблицы. Другие модули импортируют только отсюда."""

from glava.modules.source_text.blocks import (
    BARE_REFERENCE,
    REFERENCE,
    book_tables,
    number_blocks,
)
from glava.modules.source_text.units import Unit, mark_unsure, parse_units, read_pages

__all__ = [
    "BARE_REFERENCE",
    "REFERENCE",
    "Unit",
    "book_tables",
    "mark_unsure",
    "number_blocks",
    "parse_units",
    "read_pages",
]
