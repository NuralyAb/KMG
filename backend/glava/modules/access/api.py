"""Публичный вход модуля: вход автора. Другие модули импортируют только отсюда."""

from glava.modules.access.service import Access, AccessGuard

__all__ = [
    "Access",
    "AccessGuard",
]
