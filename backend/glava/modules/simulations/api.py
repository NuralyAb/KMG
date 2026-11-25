"""Публичный вход модуля: публикация симуляторов в курсе. Другие модули импортируют только отсюда."""

from glava.modules.simulations.publish import publish_simulations

__all__ = [
    "publish_simulations",
]
