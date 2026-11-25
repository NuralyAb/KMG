"""График зависимости: по формуле или точкам главы, либо качественный ход без чисел на осях."""

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from glava.scenes.canvas import FONT, LINE, PAD, W, arrow, legend, line, lines, path, text, wrap
from glava.scenes.formula import evaluate

LABEL = "симуляция"
FRAME_CLASS = "A"
SUMMARY = """plot — зависимость одной величины от другой. data: {"x_label":"до 34 знаков с единицей","y_label":"до 34 знаков с единицей","numeric":true|false,"log_x":false,"log_y":false,"y_down":false,"params":{"a":1},"series":[{"name":"до 40 знаков","color":"ключ цвета легенды или пусто","points":[[x,y],…]} или {"name":"…","formula":"a * x ** (-m)","from":0.05,"to":0.3}],"marks":[{"x":0.1,"y":5,"text":"до 24 знаков"}]}. numeric:true — все числа из главы, формула главы считается кодом (функции exp, log, log10, sqrt, sin, cos; переменная x); numeric:false — ход кривой без чисел, координаты 0..1. 1–4 кривых. Метка стоит на кривой. Глубина — только на оси y и с y_down:true."""
POINT = {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number"}}
SCHEMA = {
    "type": "object", "required": ["x_label", "y_label", "numeric", "series"], "additionalProperties": False,
    "properties": {
        "x_label": {"type": "string", "maxLength": 40}, "y_label": {"type": "string", "maxLength": 40}, "numeric": {"type": "boolean"},
        "log_x": {"type": "boolean"}, "log_y": {"type": "boolean"}, "y_down": {"type": "boolean"}, "params": {"type": "object", "additionalProperties": {"type": "number"}},
        "series": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
            "type": "object", "required": ["name"], "additionalProperties": False,
            "properties": {"name": {"type": "string", "maxLength": 48}, "color": {"type": ["string", "null"]},
                           "points": {"type": "array", "minItems": 2, "items": POINT}, "formula": {"type": "string"},
                           "from": {"type": "number"}, "to": {"type": "number"}},
            "oneOf": [{"required": ["points"]}, {"required": ["formula", "from", "to"]}]}},
        "marks": {"type": "array", "maxItems": 3, "items": {
            "type": "object", "required": ["x", "y", "text"], "additionalProperties": False,
            "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "text": {"type": "string", "maxLength": 26}}}},
    },
}
SAMPLES = 60
MARK_GAP = 0.05
PLOT_H = 300
FALLBACK = ("#F1C40F", "#3498DB", "#E84393", "#2ECC71")
LEFT, RIGHT = 76, W - PAD
Points = list[tuple[float, float]]


def points_of(series: Mapping[str, Any], data: Mapping[str, Any]) -> Points:
    if "points" in series:
        return [(float(x), float(y)) for x, y in series["points"]]
    start, end = series["from"], series["to"]
    steps = [i / (SAMPLES - 1) for i in range(SAMPLES)]
    xs = [start * (end / start) ** s for s in steps] if data.get("log_x") and start > 0 else [start + (end - start) * s for s in steps]
    return [(x, evaluate(series["formula"], {**data.get("params", {}), "x": x})) for x in xs]


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    for series in data["series"]:
        if "formula" in series and series["from"] >= series["to"]:
            issues.append(f"{series['name']}: from не меньше to")
            continue
        try:
            points = points_of(series, data)
        except ValueError as error:
            issues.append(f"{series['name']}: {error}")
            continue
        if not data["numeric"] and any(not 0 <= v <= 1 for p in points for v in p):
            issues.append(f"{series['name']}: без чисел координаты должны быть от 0 до 1")
        for axis, flag in ((0, "log_x"), (1, "log_y")):
            if data.get(flag) and any(p[axis] <= 0 for p in points):
                issues.append(f"{series['name']}: логарифмической оси нужны значения больше нуля")
    issues += _axis_issues(data, style)
    if not issues:
        issues += _mark_issues(data)
    if not data["numeric"] and (data.get("log_x") or data.get("log_y")):
        issues.append("логарифмическая ось бывает только у графика с числами")
    return issues


def _axis_issues(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    def grows_down(label: str) -> bool:
        return any(re.search(p, label.strip(), re.IGNORECASE) for p in style.get("axes_down", []))

    issues = [f"«{data['x_label']}» растёт вниз: поставь её на ось y и задай y_down:true"] if grows_down(data["x_label"]) else []
    if grows_down(data["y_label"]) != bool(data.get("y_down")):
        issues.append("y_down:true нужен только величине, которая растёт вниз, и для неё обязателен")
    return issues


def _mark_issues(data: Mapping[str, Any]) -> list[str]:
    """Метка не висит в пустоте: она лежит на одной из кривых."""
    curves = [points_of(s, data) for s in data["series"]]
    log_x, log_y = bool(data.get("log_x")), bool(data.get("log_y"))
    span_x, span_y = _spans(data, curves)
    issues = []
    for mark in data.get("marks", []):
        if (log_x and mark["x"] <= 0) or (log_y and mark["y"] <= 0):
            issues.append(f"метка «{mark['text']}»: логарифмической оси нужны значения больше нуля")
            continue
        spot = (_place(mark["x"], span_x, log_x), _place(mark["y"], span_y, log_y))
        placed = [[(_place(x, span_x, log_x), _place(y, span_y, log_y)) for x, y in c] for c in curves]
        if min(_distance(spot, a, b) for c in placed for a, b in zip(c, c[1:], strict=False)) > MARK_GAP:
            issues.append(f"метка «{mark['text']}» не лежит на кривой")
    return issues


def _distance(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _spans(data: Mapping[str, Any], curves: Sequence[Points]) -> tuple[tuple[float, float], tuple[float, float]]:
    if not data["numeric"]:
        return (0.0, 1.0), (0.0, 1.0)
    marks = data.get("marks", [])
    xs = [p[0] for c in curves for p in c] + [m["x"] for m in marks if m["x"] > 0 or not data.get("log_x")]
    ys = [p[1] for c in curves for p in c] + [m["y"] for m in marks if m["y"] > 0 or not data.get("log_y")]
    return _scale(xs, bool(data.get("log_x"))), _scale(ys, bool(data.get("log_y")))


def _color(key: str | None, index: int, style: Mapping[str, Any]) -> str:
    for group in ("curves", "fluids", "lithology"):
        if key in style.get(group, {}):
            return style[group][key]["color"]
    return FALLBACK[index % len(FALLBACK)]


def _scale(values: Sequence[float], log: bool) -> tuple[float, float]:
    low, high = min(values), max(values)
    if log:
        return 10 ** math.floor(math.log10(low)), 10 ** math.ceil(math.log10(high) + 1e-9)
    if low >= 0 and low < 0.5 * high:
        low = 0
    return (low, high) if high > low else (low - 1, high + 1)


def _place(value: float, span: tuple[float, float], log: bool) -> float:
    low, high = span
    return math.log(value / low) / math.log(high / low) if log else (value - low) / (high - low)


def _ticks(span: tuple[float, float], log: bool) -> list[float]:
    low, high = span
    if log:
        first, last = round(math.log10(low)), round(math.log10(high))
        step = max(1, (last - first + 3) // 4)
        return [10.0 ** k for k in range(first, last + 1, step)]
    raw = (high - low) / 4
    size = 10 ** math.floor(math.log10(raw))
    step = min((m * size for m in (1, 2, 2.5, 5, 10)), key=lambda s: abs(s - raw))
    start = math.ceil(low / step - 1e-9)
    return [k * step for k in range(start, start + 8) if k * step <= high + step * 1e-6]


def _tick_label(value: float) -> str:
    return f"{value:.4g}".replace(".", ",").replace("e+0", "e").replace("-", "−")


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    log_x, log_y = bool(data.get("log_x")), bool(data.get("log_y"))
    curves = [points_of(s, data) for s in data["series"]]
    marks = data.get("marks", [])
    span_x, span_y = _spans(data, curves)
    down = bool(data.get("y_down"))
    head = wrap(data["y_label"], W - 2 * PAD)
    left = LEFT if data["numeric"] else 40
    top = PAD + LINE * len(head) + 8
    bottom = top + PLOT_H

    def at(x: float, y: float) -> tuple[float, float]:
        return left + _place(x, span_x, log_x) * (RIGHT - left), (top if down else bottom) + (1 if down else -1) * _place(y, span_y, log_y) * PLOT_H

    body = lines(PAD, PAD + FONT - 2, head, style["muted"])
    if data["numeric"]:
        body += _grid(at, span_x, span_y, log_x, log_y, left, top, bottom, style)
    body += (arrow(left, top, left, bottom + 6, style["muted"], 2, 7) if down else arrow(left, bottom, left, top - 4, style["muted"], 2, 7)) + arrow(left, bottom, RIGHT + 6, bottom, style["muted"], 2, 7)
    colors = [_color(s.get("color"), i, style) for i, s in enumerate(data["series"])]
    body += "".join(path([at(*p) for p in c], color, 4) for c, color in zip(curves, colors, strict=True))
    for mark in marks:
        x, y = at(mark["x"], mark["y"])
        near_right = x > W / 2
        body += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{style["text"]}"/>'
        rows = wrap(mark["text"], (x - left - 20) if near_right else (RIGHT - x - 20))
        body += lines(x - 12 if near_right else x + 12, max(y - 12, top + FONT), rows, style["text"], "end" if near_right else "start")
    y = bottom + (LINE + 6 if data["numeric"] else 6)
    foot = wrap(data["x_label"] if data["numeric"] else f"{data['x_label']} →", W - 2 * PAD)
    body += lines(RIGHT, y + FONT, foot, style["muted"], "end")
    drawn, y = legend(list(zip(colors, (s["name"] for s in data["series"]), strict=True)), y + LINE * len(foot) + 10, style["text"])
    return body + drawn, y + 4


def _grid(at: Any, span_x: tuple[float, float], span_y: tuple[float, float], log_x: bool, log_y: bool, left: float, top: float, bottom: float,
          style: Mapping[str, Any]) -> str:
    out = ""
    for value in _ticks(span_y, log_y):
        _, y = at(span_x[0], value)
        out += line(left, y, RIGHT, y, style["panel"], 2) + text(left - 8, y + 8, _tick_label(value), style["muted"], "end")
    for value in _ticks(span_x, log_x):
        x, _ = at(value, span_y[0])
        out += line(x, top, x, bottom, style["panel"], 2) + text(min(x, RIGHT - 14), bottom + FONT + 6, _tick_label(value), style["muted"], "middle")
    return out
