"""Вход автора: запросы и ответы."""

from typing import Literal

from glava.shared.http.dto import Model


class Me(Model):
    role: Literal["admin", "learner"]
    protected: bool
