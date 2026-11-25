"""Сравнение двух случаев по признакам."""

from collections.abc import Mapping
from typing import Any

from glava.modules.drawing.canvas import (
    FONT,
    LINE,
    PAD,
    W,
    line,
    lines,
    rect,
    text,
    wrap,
)

LABEL = "схема"
FRAME_CLASS = "A"
SUMMARY = """compare — два случая рядом по признакам. data: {"left_title":"до 18 знаков","right_title":"до 18 знаков","rows":[{"aspect":"признак до 30 знаков","left":"до 44 знаков","right":"до 44 знаков"}]}. 2–6 строк."""
CELL = {"type": "string", "minLength": 1, "maxLength": 48}
SCHEMA = {
    "type": "object", "required": ["left_title", "right_title", "rows"], "additionalProperties": False,
    "properties": {
        "left_title": {"type": "string", "minLength": 2, "maxLength": 28}, "right_title": {"type": "string", "minLength": 2, "maxLength": 28},
        "rows": {"type": "array", "minItems": 2, "maxItems": 6, "items": {
            "type": "object", "required": ["aspect", "left", "right"], "additionalProperties": False,
            "properties": {"aspect": {"type": "string", "minLength": 2, "maxLength": 34}, "left": CELL, "right": CELL}}},
    },
}
HALF = (W - 2 * PAD - 16) / 2
INNER = 10


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    return [f"строка «{r['aspect']}»: случаи не различаются" for r in data["rows"] if r["left"].casefold() == r["right"].casefold()]


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    right_x = PAD + HALF + 16
    heads = [wrap(data["left_title"], HALF - 2 * INNER), wrap(data["right_title"], HALF - 2 * INNER)]
    height = max(map(len, heads)) * LINE + 14
    body = ""
    for x, rows in zip((PAD, right_x), heads, strict=True):
        body += rect(x, PAD, HALF, height, style["panel"], radius=8) + lines(x + INNER, PAD + FONT + 5, rows, style["text"], weight=600)
    y = PAD + height + 14
    for row in data["rows"]:
        body += line(PAD, y, W - PAD, y, style["panel"])
        body += text(PAD + INNER, y + FONT + 8, row["aspect"], style["muted"])
        cells = [wrap(row["left"], HALF - 2 * INNER), wrap(row["right"], HALF - 2 * INNER)]
        for x, rows in zip((PAD, right_x), cells, strict=True):
            body += lines(x + INNER, y + FONT + 8 + LINE, rows, style["text"])
        y += LINE * (1 + max(map(len, cells))) + 18
    return body, y + 4
