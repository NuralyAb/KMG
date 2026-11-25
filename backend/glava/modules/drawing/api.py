"""Публичный вход модуля: холст и шаблоны рисунков. Другие модули импортируют только отсюда."""

from glava.modules.drawing.canvas import (
    FONT,
    LINE,
    PAD,
    W,
    arrow,
    legend,
    line,
    lines,
    path,
    rect,
    text,
    wrap,
)
from glava.modules.drawing.formula import evaluate
from glava.modules.drawing.scenes import (
    load_module,
    load_style,
    load_templates,
    render,
    scene_issues,
)

__all__ = [
    "FONT",
    "LINE",
    "PAD",
    "W",
    "arrow",
    "evaluate",
    "legend",
    "line",
    "lines",
    "load_module",
    "load_style",
    "load_templates",
    "path",
    "rect",
    "render",
    "scene_issues",
    "text",
    "wrap",
]
