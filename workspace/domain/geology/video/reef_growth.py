"""Рост рифа: высота постройки и слои считаются из кривой уровня моря и предельной скорости роста."""

import json
import math
import random
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import cairo

from glava.sdk.video import LAYOUTS, arrow, dot, fill_rect, polygon, polyline, text

SUMMARY = """reef_growth — органогенная постройка растёт вслед за относительным уровнем моря. Разрез, кривая уровня моря и кривая высоты постройки считаются из одной модели: за шаг времени риф прибавляет не больше max_growth и не выше уровня моря; слишком глубоко рост останавливается (утонул), выше воды рост стоит и кровля размывается. params: {"sea":[[время 0..1, уровень м], … по возрастанию времени],"max_growth":м за единицу времени,"photic":м глубины, где организмы ещё строят,"erosion":м за единицу времени при осушении,"base":начальная глубина дна м (меньше уровня моря),"half_width":м полуширина основания,"slope":0.3..0.9 во сколько раз верх уже основания,"zones":[{"key":"core|flank|lagoon","label":"до 14 знаков"}],"observe":доля полуширины 0..1 где стоит скважина}. Числа условные, если их нет в утверждениях. Действия: time 0..1 (только вперёд), zones 0..1 (подписи зон), well 0..1 (скважина), pores 0..1 (поры в ядре), focus 0 нет, 1 разрез, 2 график, true_scale 0..1."""
STATE_MODEL = "высота постройки — интегрирование роста с пределом скорости, уровнем моря, глубиной фотической зоны и размывом при осушении"
FITS = ("риф", "биогерм", "органоген", "уровн[ьяе] моря|трансгресс|регресс", "ядр[оа]|склон|лагун", "постройк")
ACTIONS = {"time", "zones", "well", "pores", "focus", "true_scale"}
STEPS = 240
BANDS = 8


def sea_level(params: Mapping[str, Any], t: float) -> float:
    points = params["sea"]
    for (t1, v1), (t2, v2) in zip(points, points[1:], strict=False):
        if t <= t2:
            return v1 + (v2 - v1) * max(0.0, t - t1) / (t2 - t1)
    return points[-1][1]


@lru_cache(maxsize=32)
def _history_of(key: str) -> tuple[tuple[float, ...], tuple[str, ...]]:
    params = json.loads(key)
    top, heights, states = params["base"], [], []
    for i in range(STEPS + 1):
        t = i / STEPS
        room = sea_level(params, t) - top
        if room < 0:
            state, change = "осушён", -min(params["erosion"] / STEPS, -room)
        elif room > params["photic"]:
            state, change = "утонул", 0.0
        else:
            state, change = "растёт", min(params["max_growth"] / STEPS, room)
        top += change if i else 0.0
        heights.append(top)
        states.append(state)
    return tuple(heights), tuple(states)


def _history(params: Mapping[str, Any]) -> tuple[tuple[float, ...], tuple[str, ...]]:
    return _history_of(json.dumps(params, sort_keys=True))


def height(params: Mapping[str, Any], t: float) -> float:
    heights, _ = _history(params)
    place = max(0.0, min(1.0, t)) * STEPS
    low = int(place)
    return heights[low] + (heights[min(low + 1, STEPS)] - heights[low]) * (place - low)


def growth_state(params: Mapping[str, Any], t: float) -> str:
    return _history(params)[1][round(max(0.0, min(1.0, t)) * STEPS)]


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    need = ("sea", "max_growth", "photic", "erosion", "base", "half_width", "slope", "zones")
    missing = [k for k in need if k not in params]
    if missing:
        return [f"нет параметров: {', '.join(missing)}"]
    sea = params["sea"]
    issues: list[str] = []
    if len(sea) < 2 or sea[0][0] != 0 or sea[-1][0] != 1 or any(b[0] <= a[0] for a, b in zip(sea, sea[1:], strict=False)):
        return ["sea: время идёт от 0 до 1 по возрастанию"]
    if any(params[k] <= 0 for k in ("max_growth", "photic", "half_width")) or params["erosion"] < 0:
        issues.append("max_growth, photic, half_width больше нуля, erosion не меньше нуля")
    if not 0.3 <= params["slope"] <= 0.9:
        issues.append("slope от 0.3 до 0.9")
    if not 0 < sea[0][1] - params["base"] <= params["photic"]:
        issues.append("в начале дно должно быть под водой и в фотической зоне")
    if any(z["key"] not in ("core", "flank", "lagoon") or len(z["label"]) > 14 for z in params["zones"]):
        issues.append("zones: core, flank или lagoon, подпись до 14 знаков")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    times = [b["action"]["time"] for b in beats if "time" in b["action"]]
    if any(b < a for a, b in zip(times, times[1:], strict=False)) or any(not 0 <= v <= 1 for v in times):
        issues.append("time идёт только вперёд, от 0 до 1")
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"time": 0.0, "zones": 0.0, "well": 0.0, "pores": 0.0, "focus": 0.0, "true_scale": 0.0}


def _limits(params: Mapping[str, Any]) -> tuple[float, float]:
    levels = [v for _, v in params["sea"]] + list(_history(params)[0])
    span = max(levels) - min(*levels, params["base"])
    return params["base"] - span * 0.35, max(levels) + span * 0.12


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    x, y, w, h = area
    gap = layout.small * 0.5
    if layout.height > layout.width:
        return [(x, y, w, h * 0.64 - gap), (x, y + h * 0.64, w, h * 0.36)]
    return [(x, y, w * 0.62 - gap, h), (x + w * 0.62, y, w * 0.38, h)]


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Вертикальное преувеличение: считается из тех же размеров, что и рисунок."""
    _, _, w, h = _boxes(LAYOUTS[kind].scene, LAYOUTS[kind])[0]
    low, high = _limits(params)
    vertical, horizontal = h / (high - low), w / (3.2 * params["half_width"])
    return f"высота увеличена в {vertical / horizontal:.0f} раз"


def _outline(params: Mapping[str, Any], t: float, share: float) -> float:
    """Высота кровли на расстоянии share полуширины: плоский верх и склоны."""
    top, base = height(params, t), params["base"]
    if share >= 1:
        return base
    rim = params["slope"]
    return top if share <= rim else base + (top - base) * 0.5 * (1 + math.cos(math.pi * (share - rim) / (1 - rim)))


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    now = max(0.0, min(1.0, state["time"]))
    boxes = _boxes(area, layout)
    for number, (box, painter) in enumerate(zip(boxes, (_section, _chart), strict=True), start=1):
        x, y, w, h = box
        fill_rect(ctx, x, y, w, h, style["panel"], radius=14)
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        painter(ctx, box, params, state, now, style, layout)
        ctx.restore()
        if round(state["focus"]) == number and state["focus"] > 0.5:
            ctx.set_source_rgba(1, 1, 1, 0.9)
            ctx.set_line_width(6)
            ctx.rectangle(x + 3, y + 3, w - 6, h - 6)
            ctx.stroke()
    if state["true_scale"] > 0.01:
        _true_scale(ctx, boxes[0], params, now, state["true_scale"], style, layout)


def _section(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: float,
             style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    low, high = _limits(params)
    axis, half = x + w / 2, w / 3.2

    def at(level: float) -> float:
        return y + (high - level) / (high - low) * h

    water = at(sea_level(params, now))
    fill_rect(ctx, x, water, w, y + h - water, style["fluids"]["water"]["color"], 0.35)
    polyline(ctx, [(x, water), (x + w, water)], style["fluids"]["water"]["color"], 4)
    text(ctx, x + w - layout.small * 0.4, water - 10, "уровень моря", layout.small * 0.75, style["fluids"]["water"]["color"], True, "end")
    fill_rect(ctx, x, at(params["base"]), w, y + h, style["lithology"]["limestone"]["color"])
    grid = [i / 60 for i in range(61)]
    bands = [now * (i + 1) / BANDS for i in range(BANDS)] if now > 0 else []
    for number, moment in reversed(list(enumerate(bands))):
        profile = [(axis + side * share * half, at(min(_outline(params, moment, share), _outline(params, now, share)))) for side in (-1, 1) for share in (reversed(grid) if side < 0 else grid)]
        polygon(ctx, [*profile, (axis + half, at(params["base"])), (axis - half, at(params["base"]))], style["lithology"]["reef"]["color"], 1.0)
        polyline(ctx, profile, "#0F1419", 2, 0.35)
        if number % 2:
            polygon(ctx, [*profile, (axis + half, at(params["base"])), (axis - half, at(params["base"]))], "#0F1419", 0.06)
    if state["pores"] > 0.01:
        rng = random.Random(11)
        for i in range(260):
            share, level = rng.random() * params["slope"], params["base"] + rng.random() * (height(params, now) - params["base"])
            if level < _outline(params, now, share) - 1e-6:
                dot(ctx, axis + (1 if i % 2 else -1) * share * half, at(level), 4, "#0F1419", 0.5 * state["pores"])
    if state["zones"] > 0.01:
        spots = {"core": (0.0, 0.5), "flank": (0.86, 0.3), "lagoon": (-1.3, 0.06)}
        for zone in params["zones"]:
            share, level = spots[zone["key"]]
            text(ctx, axis + share * half, at(params["base"] + (height(params, now) - params["base"]) * level), zone["label"], layout.small * 0.8, "#0F1419" if zone["key"] != "lagoon" else style["text"], True, "middle", state["zones"])
    if state["well"] > 0.01:
        wx = axis + params.get("observe", 0.0) * half
        polyline(ctx, [(wx, y), (wx, at(params["base"]) + layout.small)], style["measurement"]["color"], 6, state["well"])
    arrow(ctx, x + 18, y + h - 20, x + 18, y + h - 20 - layout.small * 1.8, style["muted"], 4)
    text(ctx, x + 36, y + h - 26, "выше", layout.small * 0.75, "#0F1419")


def _chart(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: float,
           style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    low, high = _limits(params)
    left, right, top, bottom = x + w * 0.06, x + w * 0.96, y + h * 0.1, y + h * 0.72
    polyline(ctx, [(left, top), (left, bottom), (right, bottom)], style["muted"], 3)
    text(ctx, right, bottom - 10, "время →", layout.small * 0.72, style["muted"], False, "end")

    def at(moment: float, level: float) -> tuple[float, float]:
        return left + (right - left) * moment, top + (high - level) / (high - low) * (bottom - top)

    moments = [now * i / 100 for i in range(101)]
    sea, reef = style["fluids"]["water"]["color"], style["lithology"]["reef"]["color"]
    polyline(ctx, [at(m, sea_level(params, m)) for m in moments], sea, 6)
    polyline(ctx, [at(m, height(params, m)) for m in moments], reef, 8)
    dot(ctx, *at(now, sea_level(params, now)), 10, sea)
    dot(ctx, *at(now, height(params, now)), 11, reef)
    row = bottom + layout.small * 1.1
    text(ctx, left, row, "уровень моря", layout.small * 0.78, sea, True)
    text(ctx, left + w * 0.45, row, "кровля рифа", layout.small * 0.78, reef, True)
    if now > 0:
        text(ctx, left, row + layout.small * 1.1, f"состояние: {growth_state(params, now)}", layout.small * 0.85, style["text"], True)


def _true_scale(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], now: float, alpha: float, style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    fill_rect(ctx, x, y, w, h, style["background"], 0.95 * alpha, 14)
    scale, axis, floor = w / (3.2 * params["half_width"]), x + w / 2, y + h * 0.6
    grid = [i / 60 for i in range(61)]
    profile = [(axis + side * share * params["half_width"] * scale, floor - (_outline(params, now, share) - params["base"]) * scale) for side in (-1, 1) for share in (reversed(grid) if side < 0 else grid)]
    fill_rect(ctx, x, floor, w, h * 0.08, style["lithology"]["limestone"]["color"], alpha)
    polygon(ctx, [*profile, (axis + w / 3.2, floor), (axis - w / 3.2, floor)], style["lithology"]["reef"]["color"], alpha)
    text(ctx, axis, y + h * 0.2, "истинный масштаб", layout.small, style["text"], True, "middle", alpha)
