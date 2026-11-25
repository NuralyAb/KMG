"""Величины или диапазоны столбцами по строкам; числа только из главы."""

import math
from collections.abc import Mapping
from typing import Any

from glava.modules.drawing.canvas import FONT, LINE, PAD, W, lines, rect, text, wrap

LABEL = "схема"
FRAME_CLASS = "A"
SUMMARY = """bars — числа или диапазоны из главы. data: {"unit":"единица","items":[{"name":"до 40 знаков","value":12}|{"name":"…","from":5,"to":20}],"log":false}. 2–7 строк; числа и единица только из утверждений узла; log:true, если значения различаются в десятки раз."""
NUMBER = {"type": "number"}
SCHEMA = {
    "type": "object", "required": ["unit", "items"], "additionalProperties": False,
    "properties": {
        "unit": {"type": "string", "minLength": 1, "maxLength": 24}, "log": {"type": "boolean"},
        "items": {"type": "array", "minItems": 2, "maxItems": 7, "items": {
            "type": "object", "required": ["name"], "additionalProperties": False,
            "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 60}, "value": NUMBER, "from": NUMBER, "to": NUMBER},
            "oneOf": [{"required": ["value"]}, {"required": ["from", "to"]}]}},
    },
}
BAR_H = 24


def _ends(item: Mapping[str, Any]) -> tuple[float, float]:
    return (item["from"], item["to"]) if "to" in item else (0.0, item["value"])


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    issues = [f"{i['name']}: начало диапазона не меньше конца" for i in data["items"] if "to" in i and i["from"] >= i["to"]]
    values = [v for i in data["items"] for v in _ends(i) if v]
    issues += ["отрицательные числа столбцами не показать"] if any(v < 0 for v in values) else []
    return issues + (["логарифмической шкале нужны числа больше нуля"] if data.get("log") and any("to" in i and i["from"] <= 0 for i in data["items"]) else [])


def _format(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    top = max(_ends(i)[1] for i in data["items"]) or 1
    positive = [v for i in data["items"] for v in _ends(i) if v > 0]
    low = min(positive) / 2 if positive else 1
    width = W - 2 * PAD - 130

    def place(value: float) -> float:
        if not data.get("log"):
            return value / top * width
        return 0 if value <= low else math.log(value / low) / math.log(top / low) * width

    body = text(PAD, PAD + FONT, f"{data['unit']}{', логарифмическая шкала' if data.get('log') else ''}", style["muted"])
    y = float(PAD + FONT + 18)
    for item in data["items"]:
        rows = wrap(item["name"], W - 2 * PAD)
        body += lines(PAD, y + FONT - 2, rows, style["text"])
        y += LINE * len(rows) + 2
        start, end = _ends(item)
        label = f"{_format(start)}–{_format(end)}" if "to" in item else _format(end)
        x1, x2 = place(start), max(place(end), place(start) + 3)
        body += rect(PAD, y, width, BAR_H, style["panel"], radius=4) + rect(PAD + x1, y, x2 - x1, BAR_H, style["measurement"]["color"], radius=4)
        body += text(PAD + width + 10, y + 19, label, style["text"])
        y += BAR_H + 16
    return body, y
