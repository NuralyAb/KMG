"""Публичный вход модуля: паспорт переноса. Другие модули импортируют только отсюда."""

from glava.modules.transfer.passport import make_passport

__all__ = [
    "make_passport",
]
