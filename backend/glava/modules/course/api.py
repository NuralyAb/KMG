"""Публичный вход модуля: сборка курса. Другие модули импортируют только отсюда."""

from glava.modules.course.build import build_course

__all__ = [
    "build_course",
]
