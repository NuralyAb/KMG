"""Волна давления в упругом пласте: профиль, план и график на забое считаются из одной формулы линейного стока."""

import math
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import cairo

from glava.sdk.video import LAYOUTS, arrow, dot, fill_rect, polygon, polyline, text

SUMMARY = """pressure_wave — скважину пускают с постоянным дебитом, и понижение давления расходится по упругому пласту. Три синхронных вида из одной модели: разрез с профилем давления, план с кольцами, график давления во времени на забое и в наблюдательной точке. params: {"p0":начальное давление,"unit":"МПа","drop":множитель понижения Qμ/(4πkh) в тех же единицах,"kappa":пьезопроводность м²/с,"t_max":конец показа в секундах,"stop":секунда остановки скважины или null,"radius":край вида в метрах,"rw":радиус скважины м (0.1),"thickness":толщина пласта м,"observe":расстояние до наблюдательной точки м,"lith":"sand|limestone|reef"}. Числа условные, если их нет в утверждениях: тогда их не произносят. Действия: time 0..1 (доля t_max, только вперёд), observe 0..1 (наблюдательная точка), naive 0..1 (пунктир ложного ожидания: фронт с постоянной скоростью), focus 0 нет, 1 разрез, 2 план, 3 график, true_scale 0..1 (пласт в истинном масштабе)."""
STATE_MODEL = "понижение давления E1(r²/4κt) от линейного стока, после остановки — сложение двух решений; профиль, план и график из одной функции"
FITS = ("давлени", "упруг", "дебит", "пьезопроводн", "неустановивш|нестационарн", "фронт|возмущен|волна")
ACTIONS = {"time", "observe", "naive", "focus", "true_scale"}
POINTS = 110
RINGS = 44


@lru_cache(maxsize=200_000)
def e1(x: float) -> float:
    """Интегральная показательная функция E1(x): ряд при малых x, цепная дробь при больших."""
    if x <= 0:
        return math.inf
    if x > 40:
        return 0.0
    if x < 1:
        total, term = -0.5772156649 - math.log(x), 1.0
        for n in range(1, 30):
            term *= -x / n
            total -= term / n
        return total
    fraction = 0.0
    for n in range(60, 0, -1):
        fraction = n / (1 + n / (x + fraction))
    return math.exp(-x) / (x + fraction)


def drop_at(params: Mapping[str, Any], r: float, t: float) -> float:
    """Понижение давления в точке r к моменту t; остановка — такой же источник с обратным знаком."""
    r = max(r, params["rw"])
    stop = params.get("stop")
    parts = [(1.0, t), *([(-1.0, t - stop)] if stop is not None and t > stop else [])]
    return params["drop"] * sum(sign * e1(float(f"{r * r / (4 * params['kappa'] * age):.5g}")) for sign, age in parts if age > 0)


def pressure(params: Mapping[str, Any], r: float, t: float) -> float:
    return params["p0"] - drop_at(params, r, t)


def reach(params: Mapping[str, Any], t: float) -> float:
    """Радиус, где понижение ещё заметно глазу: 2√(κt). Это не граница, дальше давление тоже меняется."""
    return 2 * math.sqrt(params["kappa"] * max(t, 0.0))


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    need = ("p0", "unit", "drop", "kappa", "t_max", "radius", "rw", "thickness", "observe", "lith")
    missing = [k for k in need if k not in params]
    if missing:
        return [f"нет параметров: {', '.join(missing)}"]
    issues = [f"{k} должен быть больше нуля" for k in ("p0", "drop", "kappa", "t_max", "radius", "rw", "thickness") if params[k] <= 0]
    if issues:
        return issues
    if params["lith"] not in ("sand", "limestone", "reef"):
        issues.append("lith: sand, limestone или reef")
    if not params["rw"] < params["observe"] < params["radius"]:
        issues.append("наблюдательная точка должна быть между скважиной и краем вида")
    stop = params.get("stop")
    if stop is not None and not 0 < stop < params["t_max"]:
        issues.append("остановка должна быть внутри показанного времени")
    if drop_at(params, params["rw"], stop or params["t_max"]) >= params["p0"]:
        issues.append("давление на забое уходит ниже нуля: уменьшите drop")
    if reach(params, params["t_max"]) > params["radius"] * 1.6:
        issues.append("понижение доходит до края вида: увеличьте radius или уменьшите t_max")
    if drop_at(params, params["observe"], params["t_max"]) < params["drop"] * 0.02:
        issues.append("до наблюдательной точки понижение не доходит: поставьте её ближе")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    times = [b["action"]["time"] for b in beats if "time" in b["action"]]
    if any(b < a for a, b in zip(times, times[1:], strict=False)) or any(not 0 <= v <= 1 for v in times):
        issues.append("time идёт только вперёд, от 0 до 1")
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"time": 0.0, "observe": 0.0, "naive": 0.0, "focus": 0.0, "true_scale": 0.0}


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Вертикальное преувеличение разреза: считается из тех же размеров, что и рисунок."""
    boxes = _boxes(LAYOUTS[kind].scene, LAYOUTS[kind])
    _, _, w, h = boxes[0]
    vertical, horizontal = h * 0.26 / params["thickness"], w / (2 * params["radius"])
    return f"толщина пласта увеличена в {vertical / horizontal:.0f} раз"


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    """Разрез, план, график: в шортсе друг под другом, в разборе рядом."""
    x, y, w, h = area
    gap = layout.small * 0.5
    if layout.height > layout.width:
        low = h * 0.44
        half = (w - gap) / 2
        return [(x, y, w, h - low - gap), (x, y + h - low, half, low), (x + half + gap, y + h - low, half, low)]
    left = w * 0.42
    side = (w - left - 2 * gap) / 2
    return [(x, y, left, h), (x + left + gap, y, side, h), (x + left + side + 2 * gap, y, side, h)]


def _span(params: Mapping[str, Any]) -> float:
    """Нижняя граница шкалы давления: самое глубокое понижение за весь показ, с запасом."""
    return drop_at(params, params["rw"], params.get("stop") or params["t_max"]) * 1.12


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    now = max(state["time"], 0.0) * params["t_max"]
    boxes = _boxes(area, layout)
    for number, (box, title, painter) in enumerate(zip(boxes, ("разрез и давление", "вид сверху", "давление во времени"), (_section, _plan, _history), strict=True), start=1):
        x, y, w, h = box
        fill_rect(ctx, x, y, w, h, style["panel"], radius=14)
        text(ctx, x + layout.small * 0.5, y + layout.small * 1.1, title, layout.small * 0.85, style["muted"], True)
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        painter(ctx, (x, y + layout.small * 1.6, w, h - layout.small * 1.6), params, state, now, style, layout)
        ctx.restore()
        if round(state["focus"]) == number and state["focus"] > 0.5:
            ctx.set_source_rgba(1, 1, 1, 0.9)
            ctx.set_line_width(6)
            ctx.rectangle(x + 3, y + 3, w - 6, h - 6)
            ctx.stroke()
    if state["true_scale"] > 0.01:
        _true_scale(ctx, boxes[0], params, state["true_scale"], style, layout)


def _shade(params: Mapping[str, Any], r: float, now: float) -> float:
    """Густота цвета: степень 0.6, чтобы малое понижение вдали было видно; порядок значений не меняется."""
    return min(1.0, max(0.0, drop_at(params, r, now)) / _span(params)) ** 0.6 if now > 0 else 0.0


def _section(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: float,
             style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    axis, color = x + w / 2, style["curves"]["PRESSURE"]["color"]
    chart_h, bed_y, bed_h = h * 0.56, y + h * 0.66, h * 0.26
    fill_rect(ctx, x, y + h * 0.58, w, h * 0.42, style["lithology"]["shale"]["color"], 0.75)
    fill_rect(ctx, x, bed_y, w, bed_h, style["lithology"][params["lith"]]["color"])
    strip = w / POINTS
    for i in range(POINTS):
        r = abs((i + 0.5) / POINTS - 0.5) * 2 * params["radius"]
        x1, x2 = round(x + i * strip), round(x + (i + 1) * strip)
        fill_rect(ctx, x1, bed_y, x2 - x1, bed_h, color, 0.85 * _shade(params, r, now))

    def at(r: float, side: int) -> tuple[float, float]:
        value = pressure(params, r, now) if now > 0 else params["p0"]
        return axis + side * r / params["radius"] * w / 2, y + chart_h * (0.12 + 0.8 * (params["p0"] - value) / _span(params))

    level = y + chart_h * 0.12
    polyline(ctx, [(x, level), (x + w, level)], style["muted"], 3, 0.8, (12, 10))
    text(ctx, x + w - layout.small * 0.4, level - 8, "начальное давление", layout.small * 0.75, style["muted"], False, "end")
    grid = [params["rw"] + (params["radius"] - params["rw"]) * (i / POINTS) ** 2 for i in range(POINTS + 1)]
    for side in (-1, 1):
        polyline(ctx, [at(r, side) for r in grid], color, 7)
    if state["naive"] > 0.01 and now > 0:
        front = reach(params, params["t_max"]) * now / params["t_max"]
        for side in (-1, 1):
            fx = axis + side * min(1.0, front / params["radius"]) * w / 2
            polyline(ctx, [(fx, y), (fx, bed_y + bed_h)], style["uncertainty"]["color"], 4, state["naive"], (8, 10))
        text(ctx, axis, y + layout.small, "ложное ожидание: резкий фронт", layout.small * 0.75, style["uncertainty"]["color"], False, "middle", state["naive"])
    fill_rect(ctx, axis - 7, y, 14, bed_y + bed_h - y, "#39424D")
    working = now > 0 and (params.get("stop") is None or now < params["stop"])
    if working:
        arrow(ctx, axis, bed_y + bed_h * 0.5, axis, y + h * 0.1, style["fluids"]["oil"]["color"], 8)
        for side in (-1, 1):
            for share in (0.3, 0.7):
                arrow(ctx, axis + side * w * 0.2, bed_y + bed_h * share, axis + side * w * 0.06, bed_y + bed_h * share, style["fluids"]["oil"]["color"], 6)
    if state["observe"] > 0.01:
        px, py = at(params["observe"], 1)
        polyline(ctx, [(px, py), (px, bed_y + bed_h)], style["measurement"]["color"], 4, state["observe"], (6, 6))
        dot(ctx, px, py, 12, style["measurement"]["color"], state["observe"])
    text(ctx, x + layout.small * 0.4, bed_y + bed_h - 10, "пласт", layout.small * 0.8, "#0F1419", True)


def _plan(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: float,
          style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    cx, cy, size = x + w / 2, y + h / 2, min(w, h) * 0.47
    color = style["curves"]["PRESSURE"]["color"]
    dot(ctx, cx, cy, size, style["lithology"][params["lith"]]["color"])
    shades = cairo.RadialGradient(cx, cy, 0, cx, cy, size)
    red, green, blue = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    for i in range(RINGS + 1):
        shades.add_color_stop_rgba(i / RINGS, red, green, blue, 0.85 * _shade(params, params["radius"] * i / RINGS, now))
    ctx.set_source(shades)
    ctx.arc(cx, cy, size, 0, 6.2832)
    ctx.fill()
    if now > 0:
        ctx.set_source_rgba(1, 1, 1, 0.75)
        ctx.set_line_width(3)
        ctx.set_dash([10, 8])
        ctx.arc(cx, cy, size * min(1.0, reach(params, now) / params["radius"]), 0, 6.2832)
        ctx.stroke()
        ctx.set_dash([])
    dot(ctx, cx, cy, 9, "#0F1419")
    if state["observe"] > 0.01:
        dot(ctx, cx + size * params["observe"] / params["radius"], cy, 12, style["measurement"]["color"], state["observe"])


def _history(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: float,
             style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    left, right, top, bottom = x + w * 0.08, x + w * 0.95, y + h * 0.1, y + h * 0.74
    polyline(ctx, [(left, top), (left, bottom), (right, bottom)], style["muted"], 3)
    text(ctx, right, bottom - 10, "время →", layout.small * 0.72, style["muted"], False, "end")
    text(ctx, left + 10, bottom - layout.small * 1.1, "↓ ниже", layout.small * 0.72, style["muted"])

    def at(r: float, moment: float) -> tuple[float, float]:
        return left + (right - left) * moment / params["t_max"], top + (bottom - top) * min(1.0, drop_at(params, r, moment) / _span(params))

    stop = params.get("stop")
    if stop is not None and now >= stop:
        sx = left + (right - left) * stop / params["t_max"]
        polyline(ctx, [(sx, top), (sx, bottom)], style["muted"], 3, 0.8, (8, 8))
        text(ctx, sx, top - 4, "остановка", layout.small * 0.72, style["muted"], False, "middle")
    moments = sorted({now * (i / 90) ** 2 for i in range(91)} | ({stop + (now - stop) * (i / 40) ** 2 for i in range(41)} if stop is not None and now > stop else set()))
    curves = [(params["rw"], style["curves"]["PRESSURE"]["color"], 1.0, "забой")]
    curves += [(params["observe"], style["measurement"]["color"], state["observe"], "точка в пласте")] if state["observe"] > 0.01 else []
    for number, (r, color, alpha, label) in enumerate(curves):
        row = bottom + layout.small * (1.0 + 0.9 * number)
        dot(ctx, left + 8, row - layout.small * 0.25, 9, color, alpha)
        text(ctx, left + 26, row, label, layout.small * 0.76, color, True, "start", alpha)
        points = [at(r, m) if m > 0 else (left, top) for m in moments]
        polyline(ctx, points, color, 7, alpha)
        if now > 0:
            dot(ctx, *points[-1], 11, color, alpha)


def _true_scale(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], alpha: float, style: Mapping[str, Any], layout: Any) -> None:
    """Пласт без вертикального преувеличения: толщина и ширина в одних метрах."""
    x, y, w, h = box
    fill_rect(ctx, x, y, w, h, style["background"], 0.95 * alpha, 14)
    thick = max(1.5, params["thickness"] * w / (2 * params["radius"]))
    fill_rect(ctx, x, y + h * 0.5 - h * 0.14, w, h * 0.28, style["lithology"]["shale"]["color"], alpha * 0.75)
    fill_rect(ctx, x, y + h * 0.5 - thick / 2, w, thick, style["lithology"][params["lith"]]["color"], alpha)
    polygon(ctx, [(x + w / 2 - 2, y + h * 0.36), (x + w / 2 + 2, y + h * 0.36), (x + w / 2 + 2, y + h * 0.5), (x + w / 2 - 2, y + h * 0.5)], style["text"], alpha)
    text(ctx, x + w / 2, y + h * 0.2, "истинный масштаб", layout.small, style["text"], True, "middle", alpha)
    text(ctx, x + w / 2, y + h * 0.8, "пласт — тонкая полоса", layout.small * 0.85, style["muted"], False, "middle", alpha)
