"""Публичный вход модуля: живой факт. Другие модули импортируют только отсюда."""

from glava.modules.impact.diff import Change, snapshot
from glava.modules.impact.files import NotBuilt, look
from glava.modules.impact.spread import leftovers, spread

__all__ = [
    "Change",
    "NotBuilt",
    "leftovers",
    "look",
    "snapshot",
    "spread",
]
