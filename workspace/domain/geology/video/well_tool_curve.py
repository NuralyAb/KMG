"""Прибор в скважине и кривая: разрез, ствол, корка, фильтрат и кривые считаются из одной модели слоёв."""

import math
import random
from collections.abc import Mapping, Sequence
from typing import Any

import cairo

from glava.sdk.video import arrow, dot, fill_rect, polygon, polyline, text, wrap
from glava.sdk.video import LAYOUTS

SUMMARY = """well_tool_curve — вертикальный разрез со скважиной: слои, ствол, корка, проникновение фильтрата, прибор едет снизу вверх и пишет кривые, вычисленные из тех же слоёв. params: {"depth_top":м,"depth_bottom":м,"depth_tick":м,"tool_resolution_m":0.3,"layers":[сверху вниз {"top":м,"bottom":м,"lith":"sand|shale|limestone|dolomite|dense|salt|anhydrite","label":"до 14 знаков","fluid":"oil|gas|water" или null,"permeable":true|false,"wall":диаметр стенки в долях долота (1.0 номинал, больше 1 — каверна),"cake":толщина корки с каждой стороны в долях долота (0, если нет),"props":{"GR":число,…}}],"curves":[{"key":"CALIPER|GR|RES|SP|NEUTRON|DENSITY|SONIC","prop":"d или ключ props","label":"до 12 знаков","unit":"","min":0,"max":1}]}. Для CALIPER prop всегда "d": диаметр считает код как wall − 2·cake. 1–2 кривые. Глубины и числа условные, если их нет в утверждениях: тогда их не произносят. Действия: tool (глубина прибора, едет снизу вверх), cake 0..1, invasion 0..1, flow 0..1 (стрелки фильтрата), nominal 0..1 (линия номинального диаметра), focus (номер слоя с 1, 0 — снять), true_scale 0..1 (врезка в истинном масштабе)."""
STATE_MODEL = "слои с диаметром стенки, коркой и свойствами; ствол и кривые считаются из них по глубине прибора"
FITS = ("ствол", "корк", "фильтрат|проникновен", "прибор|зонд", "диаметр", "диаграмм|кривая|кривой")
ACTIONS = {"tool", "cake", "invasion", "flow", "nominal", "focus", "true_scale"}
SEALED = {"shale", "salt", "anhydrite", "dense"}
STEP_M = 0.05
REAL_BIT_M = 0.2


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    layers = params.get("layers") or []
    if not 2 <= len(layers) <= 6 or not 1 <= len(params.get("curves") or []) <= 2:
        return ["нужно 2–6 слоёв и 1–2 кривые"]
    issues: list[str] = []
    edges = [params["depth_top"], *(x["bottom"] for x in layers)]
    if any(x["top"] != edges[i] or x["bottom"] <= x["top"] for i, x in enumerate(layers)) or edges[-1] != params["depth_bottom"]:
        issues.append("слои должны идти сверху вниз без пропусков от depth_top до depth_bottom")
    for x in layers:
        if x["lith"] in SEALED and (x.get("permeable") or x.get("cake") or x.get("fluid")):
            issues.append(f"{x['label']}: непроницаемая порода без корки, проникновения и флюида")
        if x.get("cake") and not x.get("permeable"):
            issues.append(f"{x['label']}: корка бывает только против проницаемого слоя")
        if x["lith"] == "shale" and x["wall"] < 1:
            issues.append(f"{x['label']}: в глине ствол не уже долота")
    order = ("gas", "oil", "water")
    fluids = [(x["fluid"], x["lith"]) for x in layers if x.get("fluid")]
    issues += ["газ над нефтью, нефть над водой" for (a, la), (b, lb) in zip(fluids, fluids[1:], strict=False) if la == lb and order.index(a) > order.index(b)]
    for c in params["curves"]:
        if c["prop"] != "d" and any(c["prop"] not in x.get("props", {}) for x in layers):
            issues.append(f"кривая {c['key']}: нет свойства {c['prop']} у всех слоёв")
        if c["key"] == "CALIPER" and c["prop"] != "d":
            issues.append("CALIPER считается только из d")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    tools = [b["action"]["tool"] for b in beats if "tool" in b["action"]]
    if any(b > a for a, b in zip(tools, tools[1:], strict=False)) or any(not params["depth_top"] <= v <= params["depth_bottom"] for v in tools):
        issues.append("прибор едет снизу вверх внутри интервала")
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"tool": params["depth_bottom"], "cake": 0.0, "invasion": 0.0, "flow": 0.0, "nominal": 0.0, "focus": 0.0, "true_scale": 0.0}


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Во сколько раз ствол шире истинного: считается из тех же размеров, что и рисунок."""
    layout = LAYOUTS[kind]
    _, _, w, h = layout.scene
    section_w = w * (0.56 if len(params["curves"]) == 1 else 0.48)
    bore_px = 2 * section_w * 0.11
    metre_px = (h - layout.small * 2.4) / (params["depth_bottom"] - params["depth_top"])
    return f"ствол шире в {bore_px / (REAL_BIT_M * metre_px):.0f} раз"


def _layer(params: Mapping[str, Any], depth: float) -> Mapping[str, Any]:
    return next((x for x in params["layers"] if x["top"] <= depth < x["bottom"]), params["layers"][-1])


def _smooth(params: Mapping[str, Any], depth: float, value: Any, window: float) -> float:
    grid = [depth + (i / 8 - 0.5) * window for i in range(9)]
    inside = [min(max(d, params["depth_top"]), params["depth_bottom"] - 1e-6) for d in grid]
    return sum(value(_layer(params, d)) for d in inside) / len(inside)


def wall(params: Mapping[str, Any], depth: float) -> float:
    return _smooth(params, depth, lambda x: x["wall"], 0.4)


def cake(params: Mapping[str, Any], depth: float, grown: float) -> float:
    return grown * _smooth(params, depth, lambda x: x.get("cake") or 0.0, 0.3)


def measured(params: Mapping[str, Any], curve: Mapping[str, Any], depth: float, grown: float) -> float:
    """Показание прибора: свойство модели, усреднённое по разрешению прибора."""
    window = params.get("tool_resolution_m", 0.3)
    if curve["prop"] == "d":
        return wall(params, depth) - 2 * cake(params, depth, grown)
    return _smooth(params, depth, lambda x: x["props"][curve["prop"]], window)


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = area
    head = layout.small * 2.4
    section_w = w * (0.56 if len(params["curves"]) == 1 else 0.48)
    top, height = y + head, h - head

    def at(depth: float) -> float:
        return top + (depth - params["depth_top"]) / (params["depth_bottom"] - params["depth_top"]) * height

    ctx.save()
    ctx.rectangle(x, top, section_w, height)
    ctx.clip()
    _rocks(ctx, params, x, section_w, at, style)
    _pores(ctx, params, state, x, section_w, at, style)
    _bore(ctx, params, state, t, x, section_w, at, style)
    ctx.restore()
    _labels(ctx, params, state, x, section_w, at, style, layout)
    arrow(ctx, x + 12, y + head * 0.15, x + 12, y + head * 0.85, style["muted"], 4)
    text(ctx, x + 34, y + head * 0.66, "глубина", layout.small, style["muted"])
    track_x, track_w = x + section_w + 24, (w - section_w - 24) / len(params["curves"])
    for i, curve in enumerate(params["curves"]):
        _track(ctx, params, state, curve, (track_x + i * track_w, track_w - 14, top, height, head), at, style, layout)
    if state["true_scale"] > 0.01:
        _true_scale(ctx, params, state["true_scale"], (x, top, section_w, height), style, layout)


def _rocks(ctx: cairo.Context, params: Mapping[str, Any], x: float, w: float, at: Any, style: Mapping[str, Any]) -> None:
    for number, layer in enumerate(params["layers"]):
        y1, y2 = at(layer["top"]), at(layer["bottom"])
        fill_rect(ctx, x, y1, w, y2 - y1, style["lithology"][layer["lith"]]["color"])
        rng = random.Random(number)
        for _ in range(int(w * (y2 - y1) / 900)):
            px, py = x + rng.random() * w, y1 + rng.random() * (y2 - y1)
            if layer["lith"] == "sand":
                dot(ctx, px, py, 2.4, "#0F1419", 0.28)
            elif layer["lith"] == "shale":
                polyline(ctx, [(px, py), (px + 18, py)], "#0F1419", 2, 0.28)
            else:
                polyline(ctx, [(px, py), (px + 14, py), (px + 14, py + 8)], "#0F1419", 2, 0.22)
        polyline(ctx, [(x, y2), (x + w, y2)], "#0F1419", 2, 0.5)


def _geometry(x: float, w: float) -> tuple[float, float]:
    return x + w * 0.34, w * 0.11


def _pores(ctx: cairo.Context, params: Mapping[str, Any], state: Mapping[str, float], x: float, w: float, at: Any, style: Mapping[str, Any]) -> None:
    axis, half = _geometry(x, w)
    for number, layer in enumerate(params["layers"]):
        if not layer.get("fluid"):
            continue
        rng = random.Random(100 + number)
        y1, y2 = at(layer["top"]) + 10, at(layer["bottom"]) - 10
        front = half * layer["wall"] + w * 0.3 * math.sqrt(max(0.0, state["invasion"])) if layer.get("permeable") else 0
        for _ in range(int(w * (y2 - y1) / 700)):
            px, py = x + rng.random() * w, y1 + rng.random() * max(1.0, y2 - y1)
            near = abs(px - axis) < front
            color = style["fluids"]["filtrate" if near and state["invasion"] > 0 else layer["fluid"]]["color"]
            dot(ctx, px, py, 6, "#0F1419", 0.55)
            dot(ctx, px, py, 5, color)


def _bore(ctx: cairo.Context, params: Mapping[str, Any], state: Mapping[str, float], t: float, x: float, w: float, at: Any, style: Mapping[str, Any]) -> None:
    axis, half = _geometry(x, w)
    top, bottom = params["depth_top"], params["depth_bottom"]
    grid = [top + i * STEP_M for i in range(int((bottom - top) / STEP_M) + 1)]

    def outline(width: Any) -> list[tuple[float, float]]:
        return [(axis - half * width(d), at(d)) for d in grid] + [(axis + half * width(d), at(d)) for d in reversed(grid)]

    polygon(ctx, outline(lambda d: wall(params, d)), style["lithology"]["shale"]["color"])
    polygon(ctx, outline(lambda d: wall(params, d)), "#0F1419", 0.2)
    polygon(ctx, outline(lambda d: wall(params, d) - 2 * cake(params, d, state["cake"])), style["fluids"]["mud"]["color"])
    rng = random.Random(7)
    for _ in range(70):
        depth = top + ((rng.random() + t * 0.02) % 1) * (bottom - top)
        dot(ctx, axis + (rng.random() - 0.5) * half * 1.5, at(depth), 2.5, "#ECEFF4", 0.25)
    if state["nominal"] > 0.01:
        for side in (-1, 1):
            polyline(ctx, [(axis + side * half, at(top)), (axis + side * half, at(bottom))], style["text"], 3, 0.9 * state["nominal"], (14, 10))
    if state["flow"] > 0.01:
        for layer in (v for v in params["layers"] if v.get("permeable")):
            for share in (0.3, 0.7):
                y = at(layer["top"] + (layer["bottom"] - layer["top"]) * share)
                for side in (-1, 1):
                    arrow(ctx, axis + side * half * 0.5, y, axis + side * half * 2.1, y, style["fluids"]["filtrate"]["color"], 7, state["flow"])
    _tool(ctx, params, state, axis, half, at, style)


def _tool(ctx: cairo.Context, params: Mapping[str, Any], state: Mapping[str, float], axis: float, half: float, at: Any, style: Mapping[str, Any]) -> None:
    y, color = at(state["tool"]), style["measurement"]["color"]
    polyline(ctx, [(axis, at(params["depth_top"])), (axis, y - 60)], style["text"], 4)
    fill_rect(ctx, axis - 13, y - 62, 26, 124, "#39424D", radius=12)
    fill_rect(ctx, axis - 13, y - 10, 26, 20, color)
    if any(c["key"] == "CALIPER" for c in params["curves"]):
        reach = half * (wall(params, state["tool"]) - 2 * cake(params, state["tool"], state["cake"]))
        for side in (-1, 1):
            polyline(ctx, [(axis + side * 10, y - 44), (axis + side * reach, y)], color, 6)
            dot(ctx, axis + side * reach, y, 8, color)


def _labels(ctx: cairo.Context, params: Mapping[str, Any], state: Mapping[str, float], x: float, w: float, at: Any, style: Mapping[str, Any], layout: Any) -> None:
    for number, layer in enumerate(params["layers"], start=1):
        y1, y2 = at(layer["top"]), at(layer["bottom"])
        rows = wrap(ctx, layer["label"], layout.small, w * 0.4, True)
        y = (y1 + y2) / 2 - (len(rows) - 1) * layout.small * 0.58 + layout.small * 0.35
        for i, row in enumerate(rows):
            text(ctx, x + w * 0.97, y + i * layout.small * 1.16, row, layout.small, "#0F1419", True, "end")
        if round(state["focus"]) == number and state["focus"] > 0.5:
            ctx.set_source_rgba(1, 1, 1, 0.9)
            ctx.set_line_width(7)
            ctx.rectangle(x + 4, y1 + 4, w - 8, y2 - y1 - 8)
            ctx.stroke()


def _track(ctx: cairo.Context, params: Mapping[str, Any], state: Mapping[str, float], curve: Mapping[str, Any], box: tuple[float, float, float, float, float],
           at: Any, style: Mapping[str, Any], layout: Any) -> None:
    x, w, top, height, head = box
    color = style["curves"][curve["key"]]["color"]
    fill_rect(ctx, x, top, w, height, style["panel"], radius=10)
    text(ctx, x + w / 2, top - head * 0.5, curve["label"], layout.small, color, True, "middle")
    text(ctx, x + w / 2, top - head * 0.08, "больше →", layout.small * 0.8, style["muted"], False, "middle")
    low, high = curve["min"], curve["max"]

    def place(value: float) -> float:
        return x + min(1.0, max(0.0, (value - low) / (high - low))) * w

    depth = params["depth_top"]
    while depth <= params["depth_bottom"]:
        polyline(ctx, [(x, at(depth)), (x + w, at(depth))], style["muted"], 1.5, 0.25)
        depth += params.get("depth_tick", 2)
    if curve["prop"] == "d" and state["nominal"] > 0.01:
        polyline(ctx, [(place(1.0), top), (place(1.0), top + height)], style["text"], 3, 0.8 * state["nominal"], (14, 10))
    count = int((params["depth_bottom"] - state["tool"]) / STEP_M)
    depths = [params["depth_bottom"] - i * STEP_M for i in range(count + 1)]
    points = [(place(measured(params, curve, d, state["cake"])), at(d)) for d in depths]
    polyline(ctx, points, color, 8)
    if len(points) > 1:
        dot(ctx, *points[-1], 12, color)


def _true_scale(ctx: cairo.Context, params: Mapping[str, Any], alpha: float, box: tuple[float, float, float, float], style: Mapping[str, Any], layout: Any) -> None:
    """Врезка: ствол в истинной ширине относительно интервала глубин."""
    x, top, w, height = box
    fill_rect(ctx, x, top, w, height, style["background"], 0.94 * alpha, 10)
    span = params["depth_bottom"] - params["depth_top"]
    scale = height * 0.86 / span
    y0 = top + height * 0.12
    for layer in params["layers"]:
        fill_rect(ctx, x + w * 0.08, y0 + (layer["top"] - params["depth_top"]) * scale, w * 0.84, (layer["bottom"] - layer["top"]) * scale,
                  style["lithology"][layer["lith"]]["color"], alpha)
    fill_rect(ctx, x + w * 0.5 - REAL_BIT_M * scale / 2, y0, REAL_BIT_M * scale, span * scale, style["fluids"]["mud"]["color"], alpha)
    text(ctx, x + w / 2, top + height * 0.08, "истинный масштаб", layout.small, style["text"], True, "middle", alpha)
