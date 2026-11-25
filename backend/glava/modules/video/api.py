"""Публичный вход модуля: ролики. Другие модули импортируют только отсюда."""

from glava.modules.video.produce import produce
from glava.modules.video.spec import make_spec

__all__ = [
    "make_spec",
    "produce",
]
