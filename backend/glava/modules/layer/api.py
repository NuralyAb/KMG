"""Публичный вход модуля: учебный слой. Другие модули импортируют только отсюда."""

from glava.modules.layer.builder import (
    coverage_rows,
    drop_unsupported,
    make_node,
    make_plan,
    pages_of,
    plan_issues,
)
from glava.modules.layer.enrich import apply, make_enrichment, sentences

__all__ = [
    "apply",
    "coverage_rows",
    "drop_unsupported",
    "make_enrichment",
    "make_node",
    "make_plan",
    "pages_of",
    "plan_issues",
    "sentences",
]
