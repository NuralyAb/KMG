"""Публичный вход модуля: рисунки. Другие модули импортируют только отсюда."""

from glava.modules.illustrations.generator import make_illustrations, records

__all__ = [
    "make_illustrations",
    "records",
]
