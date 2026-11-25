"""Публичный вход модуля: задания. Другие модули импортируют только отсюда."""

from glava.modules.tasks.generator import (
    chapter_task_issues,
    groups,
    make_tasks,
    number_tasks,
)

__all__ = [
    "chapter_task_issues",
    "groups",
    "make_tasks",
    "number_tasks",
]
