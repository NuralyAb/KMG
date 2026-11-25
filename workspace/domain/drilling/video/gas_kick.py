"""Газовая пачка в скважине: разрез, давления и объём в ёмкости считаются из одной модели газа."""

import math
import random
from collections.abc import Mapping, Sequence
from typing import Any

import cairo

from glava.sdk.video import LAYOUTS, arrow, dot, fill_rect, polyline, text

SUMMARY = """gas_kick — пачка газа всплывает в скважине. Разрез скважины с пачкой, шкалы давления на устье и на забое и прирост объёма в приёмной ёмкости считаются из одной модели: закон Бойля при постоянной температуре и гидростатика раствора. В открытой скважине газ расширяется, сильнее всего у устья, и забойное давление падает; в закрытой объём почти не меняется, и давление растёт по всему стволу. params: {"depth":глубина м,"density":плотность раствора кг/м³,"area":площадь затруба м²,"gas":объём пачки на забое м³,"hole_mm":диаметр ствола мм,"casing":глубина башмака колонны м,"formation":пластовое давление МПа или null}. Числа условные, если их нет в утверждениях. Действия: open 0..1 (подъём при открытом устье; 1 — глубина, выше которой скважина начинает разгружаться сама), closed 0..1 (доля подъёма при закрытом устье; закрыть можно в любой момент, подъём продолжается с места), shut 0..1 (превентор закрыт), scales 0..1 (шкалы давления), pit 0..1 (приёмная ёмкость), focus 0 нет, 1 скважина, 2 давления, 3 ёмкость, true_scale 0..1."""
STATE_MODEL = "пачка газа по закону Бойля в столбе раствора; открытое устье — расширение и прирост в ёмкости, закрытое — рост давления по стволу"
FITS = ("газ(?!о)", "выброс|проявлен|гнвп|газонефтеводопроявлен", "забойн", "превентор|закрыт", "всплыв|пачк", "приёмн|ёмкост", "гидростат")
ACTIONS = {"open", "closed", "shut", "scales", "pit", "focus", "true_scale"}
DISCRETE = ("focus", "shut")
ATMOSPHERE = 0.101325
GRAVITY = 9.81e-6


def _column(params: Mapping[str, Any], metres: float) -> float:
    """Давление столба раствора, МПа."""
    return params["density"] * GRAVITY * metres


def highest(params: Mapping[str, Any]) -> float:
    """Глубина верха пачки, выше которой газ выталкивает раствор быстрее, чем всплывает: дальше скважина разгружается сама и модель не годится."""
    start = params["depth"] - params["gas"] / params["area"]
    strength = (ATMOSPHERE + _column(params, start)) * params["gas"] / params["area"] * params["density"] * GRAVITY
    return max(0.0, (math.sqrt(strength) - ATMOSPHERE) / (params["density"] * GRAVITY))


def opened(params: Mapping[str, Any], share: float) -> dict[str, float]:
    """Открытое устье: над пачкой столб раствора до устья, избыток раствора вылился в ёмкость."""
    start = params["depth"] - params["gas"] / params["area"]
    top = start + (highest(params) - start) * share
    pressure = ATMOSPHERE + _column(params, top)
    volume = params["gas"] * (ATMOSPHERE + _column(params, start)) / pressure
    bottom = top + volume / params["area"]
    return {"top": top, "bottom": bottom, "volume": volume, "gas": pressure, "surface": 0.0, "hole": pressure + _column(params, params["depth"] - bottom)}


def closed(params: Mapping[str, Any], start: Mapping[str, float], share: float) -> dict[str, float]:
    """Закрытое устье: объём и давление пачки постоянны, поэтому давление над ней и под ней растёт."""
    length = start["volume"] / params["area"]
    top = start["top"] * (1 - share)
    pressure = start["gas"]
    return {"top": top, "bottom": top + length, "volume": start["volume"], "gas": pressure, "surface": pressure - ATMOSPHERE - _column(params, top),
            "hole": pressure + _column(params, params["depth"] - top - length)}


def well(params: Mapping[str, Any], state: Mapping[str, float]) -> dict[str, float]:
    before = opened(params, max(0.0, min(1.0, state["open"])))
    return closed(params, before, max(0.0, min(1.0, state["closed"]))) if state["closed"] > 0 else before


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    need = ("depth", "density", "area", "gas", "hole_mm", "casing")
    missing = [k for k in need if k not in params]
    if missing:
        return [f"нет параметров: {', '.join(missing)}"]
    issues = [f"{k} должен быть больше нуля" for k in need if params[k] <= 0]
    if issues:
        return issues
    if not 900 <= params["density"] <= 2400:
        issues.append("плотность раствора от 900 до 2400 кг/м³")
    if params["gas"] / params["area"] > params["depth"] * 0.3:
        issues.append("пачка длиннее трети скважины: уменьшите gas")
    if highest(params) > params["depth"] * 0.7:
        issues.append("пачка велика для такой глубины: уменьшите gas")
    if not 0 < params["casing"] < params["depth"]:
        issues.append("башмак колонны должен быть выше забоя")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    for key in ("open", "closed"):
        values = [b["action"][key] for b in beats if key in b["action"]]
        if any(b < a for a, b in zip(values, values[1:], strict=False)) or any(not 0 <= v <= 1 for v in values):
            issues.append(f"{key}: пачка только всплывает, от 0 до 1")
    shut = 0.0
    for beat in beats:
        shut = beat["action"].get("shut", shut)
        if beat["action"].get("closed", 0) > 0 and shut < 0.5:
            issues.append("closed: сначала закройте превентор действием shut")
        if "open" in beat["action"] and shut > 0.5 and beat["action"]["open"] > max((b["action"].get("open", 0) for b in beats[: beats.index(beat)]), default=0):
            issues.append("open: превентор уже закрыт, используйте closed")
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"open": 0.0, "closed": 0.0, "shut": 0.0, "scales": 0.0, "pit": 0.0, "focus": 0.0, "true_scale": 0.0}


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    x, y, w, h = area
    gap = layout.small * 0.5
    left = w * 0.5 if layout.height > layout.width else w * 0.4
    right = w - left - gap
    if layout.height > layout.width:
        return [(x, y, left, h), (x + left + gap, y, right, h * 0.6 - gap), (x + left + gap, y + h * 0.6, right, h * 0.4)]
    half = (right - gap) / 2
    return [(x, y, left, h), (x + left + gap, y, half, h), (x + left + half + 2 * gap, y, half, h)]


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Во сколько раз ствол шире истинного: считается из тех же размеров, что и рисунок."""
    _, _, w, h = _boxes(LAYOUTS[kind].scene, LAYOUTS[kind])[0]
    return f"ствол шире в {(w * 0.3 / (params['hole_mm'] / 1000)) / (h * 0.8 / params['depth']):.0f} раз"


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    now = well(params, state)
    boxes = _boxes(area, layout)
    shown = (1.0, state["scales"], state["pit"])
    for number, (box, painter, alpha) in enumerate(zip(boxes, (_bore, _scales, _pit), shown, strict=True), start=1):
        if alpha < 0.02:
            continue
        x, y, w, h = box
        fill_rect(ctx, x, y, w, h, style["panel"], alpha, 14)
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        painter(ctx, box, params, state, now, alpha, t, style, layout)
        ctx.restore()
        if round(state["focus"]) == number and state["focus"] > 0.5:
            ctx.set_source_rgba(1, 1, 1, 0.9)
            ctx.set_line_width(6)
            ctx.rectangle(x + 3, y + 3, w - 6, h - 6)
            ctx.stroke()
    if state["true_scale"] > 0.01:
        _true_scale(ctx, boxes[0], params, state["true_scale"], style, layout)


def _bore(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: Mapping[str, float], alpha: float,
          t: float, style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    axis, half, top, height = x + w * 0.5, w * 0.15, y + h * 0.14, h * 0.8

    def at(depth: float) -> float:
        return top + depth / params["depth"] * height

    fill_rect(ctx, x, top, w, height + h * 0.06, style["lithology"]["shale"]["color"], 0.7)
    fill_rect(ctx, x, at(params["depth"] * 0.93), w, height * 0.13, style["lithology"]["sand"]["color"])
    fill_rect(ctx, axis - half, top, 2 * half, height, style["fluids"]["mud"]["color"])
    for side in (-1, 1):
        fill_rect(ctx, axis + side * half - 5, top, 10, at(params["casing"]) - top, style["steel"]["color"])
    fill_rect(ctx, axis - half * 0.3, top, half * 0.6, height * 0.97, style["steel"]["color"], 0.9)
    y1, y2 = at(now["top"]), at(now["bottom"])
    if y2 - y1 < 14:
        y1 = y2 - 14
    for side in (-1, 1):
        left = axis + half * 0.3 if side > 0 else axis - half
        fill_rect(ctx, left, y1, half * 0.7, y2 - y1, style["fluids"]["gas"]["color"], 0.85)
    rng = random.Random(3)
    for _ in range(40):
        side = rng.choice((-1, 1))
        dot(ctx, axis + side * half * (0.35 + 0.55 * rng.random()), y1 + ((rng.random() + t * 0.08) % 1) * (y2 - y1), 4, "#FFFFFF", 0.4)
    shut = state["shut"] > 0.5
    color = style["measurement"]["color"] if shut else style["muted"]
    fill_rect(ctx, axis - half * 1.5, top - h * 0.055, half * 3, h * 0.04, color, radius=6)
    text(ctx, axis, top - h * 0.075, "превентор закрыт" if shut else "устье открыто", layout.small * 0.8, color, True, "middle")
    arrow(ctx, x + 18, top + 10, x + 18, top + 10 + layout.small * 2, style["muted"], 4)
    text(ctx, x + 34, top + layout.small * 1.6, "глубина", layout.small * 0.75, "#0F1419")
    text(ctx, x + w - 12, at(params["depth"] * 0.965), "пласт", layout.small * 0.75, "#0F1419", True, "end")
    text(ctx, x + w - 12, at(params["casing"]) + 6, "башмак", layout.small * 0.7, "#0F1419", False, "end")


def _limits(params: Mapping[str, Any]) -> float:
    return max(closed(params, opened(params, 0.0), 1.0)["hole"], params.get("formation") or 0) * 1.08


def _scales(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: Mapping[str, float], alpha: float,
            t: float, style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    limit, top, bottom = _limits(params), y + h * 0.2, y + h * 0.84
    text(ctx, x + w / 2, y + layout.small * 1.2, "давление", layout.small * 0.85, style["muted"], True, "middle", alpha)
    for share, key, label, color in ((0.28, "surface", "устье", style["curves"]["SURFACE"]["color"]), (0.72, "hole", "забой", style["curves"]["PRESSURE"]["color"])):
        cx, level = x + w * share, bottom - (bottom - top) * max(0.0, now[key]) / limit
        fill_rect(ctx, cx - w * 0.09, top, w * 0.18, bottom - top, style["background"], alpha, 8)
        fill_rect(ctx, cx - w * 0.09, level, w * 0.18, bottom - level, color, alpha, 4)
        text(ctx, cx, bottom + layout.small, label, layout.small * 0.8, color, True, "middle", alpha)
    if params.get("formation"):
        level = bottom - (bottom - top) * params["formation"] / limit
        polyline(ctx, [(x + w * 0.56, level), (x + w * 0.9, level)], style["text"], 4, alpha, (10, 8))
        text(ctx, x + w * 0.96, level - 10, "пластовое", layout.small * 0.7, style["text"], False, "end", alpha)


def _pit(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: Mapping[str, float], alpha: float,
         t: float, style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    gain = now["volume"] - params["gas"]
    largest = max(opened(params, i / 60)["volume"] for i in range(61)) - params["gas"]
    text(ctx, x + w / 2, y + layout.small * 1.2, "приёмная ёмкость", layout.small * 0.8, style["muted"], True, "middle", alpha)
    left, right, top, bottom = x + w * 0.18, x + w * 0.82, y + h * 0.3, y + h * 0.82
    base = top + (bottom - top) * 0.62
    level = base - (base - top) * min(1.0, gain / max(largest, 1e-6))
    fill_rect(ctx, left, level, right - left, bottom - level, style["fluids"]["mud"]["color"], alpha)
    polyline(ctx, [(left, top), (left, bottom), (right, bottom), (right, top)], style["text"], 5, alpha)
    polyline(ctx, [(left, base), (right, base)], style["muted"], 3, alpha, (8, 8))
    word = "объём растёт" if gain > largest * 0.02 and state["shut"] < 0.5 else "объём не меняется"
    text(ctx, x + w / 2, bottom + layout.small * 1.1, word, layout.small * 0.78, style["text"], True, "middle", alpha)


def _true_scale(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], alpha: float, style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    fill_rect(ctx, x, y, w, h, style["background"], 0.95 * alpha, 14)
    width = params["hole_mm"] / 1000 * h * 0.8 / params["depth"]
    polyline(ctx, [(x + w / 2, y + h * 0.16), (x + w / 2, y + h * 0.96)], style["text"], max(1.0, width), alpha)
    text(ctx, x + w / 2, y + h * 0.08, "истинный масштаб", layout.small * 0.85, style["text"], True, "middle", alpha)


def expansion(params: Mapping[str, Any]) -> float:
    """Во сколько раз пачка вырастет у устья в открытой скважине."""
    return opened(params, 1.0)["volume"] / params["gas"] if params["gas"] else math.inf
