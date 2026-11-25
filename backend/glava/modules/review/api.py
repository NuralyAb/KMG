"""Публичный вход модуля: проверка чужого пакета. Другие модули импортируют только отсюда."""

from glava.modules.review.engine import load_package, review_package, workspace

__all__ = [
    "load_package",
    "review_package",
    "workspace",
]
