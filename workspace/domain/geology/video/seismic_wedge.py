"""Клин в сейсмике: разрез, сейсмический разрез, трасса и график амплитуда-толщина считаются из одной модели отражения."""

import json
import math
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import cairo

from glava.sdk.video import LAYOUTS, dot, fill_rect, polygon, polyline, text

SUMMARY = """seismic_wedge — пласт-клин между вмещающими породами: толщина растёт от нуля (выклинивание слева) до max_thickness справа. Сейсмическая трасса — свёртка импульса Рикера с двумя коэффициентами отражения (кровля и подошва), поэтому разрез, сейсмический разрез, отдельная трасса и график «амплитуда — толщина» считаются из одной модели. Толстый пласт даёт два отдельных отражения; около четверти длины волны они складываются (настройка, tuning) и амплитуда наибольшая; тоньше — пласт не разрешается (видимая толщина перестаёт уменьшаться), но обнаруживается по амплитуде, пока она выше шума. Для импульса Рикера максимум приходится примерно на 0,2 λ, правило λ/4 приближённое: в кадре подписаны обе отметки. params: {"host_lith":"shale|limestone|dense|salt|anhydrite|sand","host_v":м/с,"host_rho":г/см³,"layer_lith":"sand|limestone|dolomite|reef|shale|dense","layer_v":м/с,"layer_rho":г/см³,"freq":пиковая частота импульса Гц (10–80),"max_thickness":м (0,5–3 длины волны в пласте),"width":м длина клина,"noise":доля амплитуды одной границы, ниже которой отражение тонет в шуме (0..0.5),"polarity":"normal|reverse"}. Числа условные, если их нет в утверждениях: тогда их не произносят. Действия: trace 0..1 (где стоит трасса: 0 — выклинивание, 1 — толстый край; график строится от толстого края до трассы), seismic 0..1 (показать сейсмический разрез), tuning 0..1 (отметки настройки и λ/4, зоны «разрешается / видна по амплитуде / не видна»), naive 0..1 (пунктир ложного ожидания: сейсмика как фотография, амплитуда не зависит от толщины), focus 0 нет, 1 разрез, 2 трасса, 3 график, true_scale 0..1 (клин в истинном масштабе)."""
STATE_MODEL = "трасса — свёртка импульса Рикера с коэффициентами отражения кровли и подошвы; разрез, трасса и график амплитуда-толщина из одной функции"
FITS = ("сейсм", "отражени|отражающ", "амплитуд", "тонк|клин|выклин", "разрешени|разрешает|разреша|различ", "длин[аыу] волны|частот|импульс")
ACTIONS = {"trace", "seismic", "tuning", "naive", "focus", "true_scale"}
LITHS = {"shale", "limestone", "dolomite", "reef", "sand", "dense", "salt", "anhydrite"}
TRACES = 30
SAMPLES = 240
CURVE = 160


def ricker(t: float, freq: float) -> float:
    """Импульс Рикера с пиковой частотой freq: положительный пик в нуле, два отрицательных боковых лепестка."""
    a = (math.pi * freq * t) ** 2
    return (1 - 2 * a) * math.exp(-a)


def impedance(params: Mapping[str, Any], part: str) -> float:
    return params[f"{part}_v"] * params[f"{part}_rho"]


def reflections(params: Mapping[str, Any]) -> tuple[float, float]:
    """Коэффициенты отражения кровли и подошвы: (Z2 − Z1)/(Z2 + Z1); снизу та же вмещающая порода, знак обратный."""
    z1, z2 = impedance(params, "host"), impedance(params, "layer")
    top = (z2 - z1) / (z2 + z1)
    return top, -top


def wavelength(params: Mapping[str, Any]) -> float:
    return params["layer_v"] / params["freq"]


def window(params: Mapping[str, Any]) -> tuple[float, float]:
    """Окно времени (двойное время от кровли, с): от импульса над кровлей до импульса под подошвой самого толстого места."""
    lead = 1.5 / params["freq"]
    return -lead, 2 * params["max_thickness"] / params["layer_v"] + lead


def trace(params: Mapping[str, Any], thickness: float, count: int = SAMPLES) -> list[tuple[float, float]]:
    """Отсчёты трассы (время, амплитуда) с учётом полярности показа."""
    top, base = reflections(params)
    delay = 2 * max(thickness, 0.0) / params["layer_v"]
    start, end = window(params)
    sign = 1 if params["polarity"] == "normal" else -1
    times = [start + (end - start) * i / (count - 1) for i in range(count)]
    return [(t, sign * (top * ricker(t, params["freq"]) + base * ricker(t - delay, params["freq"]))) for t in times]


def amplitude(params: Mapping[str, Any], thickness: float) -> float:
    """Наибольшая амплитуда трассы в долях амплитуды одной границы: 1 у толстого пласта, больше 1 в настройке, к нулю при выклинивании."""
    period = 1 / params["freq"]
    delay = 2 * max(thickness, 0.0) / params["layer_v"]
    times = [-period + (delay + 2 * period) * i / 400 for i in range(401)]
    return max(abs(ricker(t, params["freq"]) - ricker(t - delay, params["freq"])) for t in times)


def apparent(params: Mapping[str, Any], thickness: float) -> float:
    """Видимая толщина: расстояние между экстремумами отражений кровли и подошвы, пересчитанное в метры."""
    period = 1 / params["freq"]
    delay = 2 * max(thickness, 1e-6) / params["layer_v"]
    times = [-period + (delay + 2 * period) * i / 1200 for i in range(1201)]
    values = [(t, ricker(t, params["freq"]) - ricker(t - delay, params["freq"])) for t in times]
    first = max((p for p in values if p[0] <= delay / 2), key=lambda p: p[1])
    second = min((p for p in values if p[0] > delay / 2), key=lambda p: p[1])
    return (second[0] - first[0]) * params["layer_v"] / 2


@lru_cache(maxsize=64)
def _curve_of(key: str) -> tuple[tuple[float, float], ...]:
    params = json.loads(key)
    return tuple((params["max_thickness"] * i / CURVE, amplitude(params, params["max_thickness"] * i / CURVE)) for i in range(CURVE + 1))


def curve(params: Mapping[str, Any]) -> tuple[tuple[float, float], ...]:
    return _curve_of(json.dumps(dict(params), sort_keys=True))


def tuning(params: Mapping[str, Any]) -> float:
    """Толщина настройки: где амплитуда наибольшая."""
    return max(curve(params), key=lambda p: p[1])[0]


def detection(params: Mapping[str, Any]) -> float:
    """Самая малая толщина, при которой амплитуда ещё выше шума."""
    return next((h for h, a in curve(params) if a > params["noise"]), params["max_thickness"])


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    need = ("host_lith", "host_v", "host_rho", "layer_lith", "layer_v", "layer_rho", "freq", "max_thickness", "width", "noise", "polarity")
    missing = [k for k in need if k not in params]
    if missing:
        return [f"нет параметров: {', '.join(missing)}"]
    issues = [f"{k} должен быть больше нуля" for k in ("host_v", "host_rho", "layer_v", "layer_rho", "freq", "max_thickness", "width") if params[k] <= 0]
    if issues:
        return issues
    if params["host_lith"] not in LITHS or params["layer_lith"] not in LITHS:
        issues.append("литология: shale, sand, limestone, dolomite, reef, dense, salt, anhydrite")
    if not 1500 <= params["host_v"] <= 7000 or not 1500 <= params["layer_v"] <= 7000:
        issues.append("скорость в породе от 1500 до 7000 м/с")
    if not 1.5 <= params["host_rho"] <= 3.2 or not 1.5 <= params["layer_rho"] <= 3.2:
        issues.append("плотность породы от 1,5 до 3,2 г/см³")
    if not 10 <= params["freq"] <= 80:
        issues.append("частота импульса от 10 до 80 Гц")
    if abs(reflections(params)[0]) < 0.02:
        issues.append("импедансы почти равны: отражения нет, клин не виден")
    lam = wavelength(params)
    if not 0.5 * lam <= params["max_thickness"] <= 3 * lam:
        issues.append(f"max_thickness от 0,5 до 3 длин волны в пласте ({lam:.0f} м): иначе настройку не показать")
    if params["width"] < 10 * params["max_thickness"]:
        issues.append("клин слишком короткий: width не меньше 10 max_thickness")
    if not 0 <= params["noise"] <= 0.5:
        issues.append("noise от 0 до 0.5")
    if params["polarity"] not in ("normal", "reverse"):
        issues.append("polarity: normal или reverse")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    issues += ["trace от 0 до 1" for b in beats if not 0 <= b["action"].get("trace", 0) <= 1]
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"trace": 0.9, "seismic": 0.0, "tuning": 0.0, "naive": 0.0, "focus": 0.0, "true_scale": 0.0}


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    """Разрезы, трасса, график: в шортсе разрезы сверху, в разборе слева."""
    x, y, w, h = area
    gap = layout.small * 0.5
    if layout.height > layout.width:
        low = h * 0.5
        side = w * 0.34
        return [(x, y, w, h - low - gap), (x, y + h - low, side, low), (x + side + gap, y + h - low, w - side - gap, low)]
    left, side = w * 0.46, w * 0.17
    return [(x, y, left, h), (x + left + gap, y, side, h), (x + left + side + 2 * gap, y, w - left - side - 2 * gap, h)]


def _split(box: tuple[float, float, float, float], layout: Any) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Внутри первого окна: сверху разрез в глубинах, снизу сейсмический разрез во времени."""
    x, y, w, h = box
    top = y + layout.small * 1.6
    depth_h = (h - layout.small * 1.6) * 0.36
    return (x + 12, top, w - 24, depth_h), (x + 12, top + depth_h + layout.small * 1.4, w - 24, y + h - top - depth_h - layout.small * 2.6)


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Вертикальное преувеличение разреза в глубинах: из тех же размеров, что и рисунок."""
    layout = LAYOUTS[kind]
    (_, _, w, h), _ = _split(_boxes(layout.scene, layout)[0], layout)
    vertical, horizontal = h / (3 * params["max_thickness"]), w / params["width"]
    return f"толщина клина увеличена в {times_word(vertical / horizontal)}"


def times_word(factor: float) -> str:
    """«в 3 раза», «в 12 раз»."""
    number = round(factor)
    return f"{number} раза" if number % 10 in (2, 3, 4) and number % 100 not in (12, 13, 14) else f"{number} раз"


def _loudest(params: Mapping[str, Any]) -> float:
    """Наибольшая амплитуда трасс клина в тех же единицах, что и отсчёты трассы."""
    return abs(reflections(params)[0]) * max(a for _, a in curve(params))


def _thickness(params: Mapping[str, Any], share: float) -> float:
    return params["max_thickness"] * max(0.0, min(1.0, share))


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    boxes = _boxes(area, layout)
    titles = ("разрез и сейсмика", "трасса", "амплитуда и толщина")
    for number, (box, title, painter) in enumerate(zip(boxes, titles, (_sections, _trace, _chart), strict=True), start=1):
        x, y, w, h = box
        fill_rect(ctx, x, y, w, h, style["panel"], radius=14)
        text(ctx, x + layout.small * 0.5, y + layout.small * 1.1, title, layout.small * 0.85, style["muted"], True)
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        painter(ctx, box, params, state, style, layout)
        ctx.restore()
        if round(state["focus"]) == number and state["focus"] > 0.5:
            ctx.set_source_rgba(1, 1, 1, 0.9)
            ctx.set_line_width(6)
            ctx.rectangle(x + 3, y + 3, w - 6, h - 6)
            ctx.stroke()
    if state["true_scale"] > 0.01:
        _true_scale(ctx, boxes[0], params, state["true_scale"], style, layout)


def _wiggle(ctx: cairo.Context, x0: float, samples: Sequence[tuple[float, float]], at_time: Any, gain: float, style: Mapping[str, Any], width: float,
            alpha: float) -> None:
    """Трасса «переменная площадь»: положительные значения закрашены."""
    points = [(x0 + value * gain, at_time(moment)) for moment, value in samples]
    filled = [(x0 + max(0.0, value) * gain, at_time(moment)) for moment, value in samples]
    polygon(ctx, [(x0, filled[0][1]), *filled, (x0, filled[-1][1])], style["text"], 0.85 * alpha)
    polyline(ctx, points, style["text"], width, alpha)


def _sections(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
              style: Mapping[str, Any], layout: Any) -> None:
    depth, seismic = _split(box, layout)
    dx, dy, dw, dh = depth
    host, layer = style["lithology"][params["host_lith"]]["color"], style["lithology"][params["layer_lith"]]["color"]
    unit = dh / (3 * params["max_thickness"])
    roof = dy + params["max_thickness"] * unit
    fill_rect(ctx, dx, dy, dw, dh, host)
    polygon(ctx, [(dx, roof), (dx + dw, roof), (dx + dw, roof + params["max_thickness"] * unit)], layer)
    text(ctx, dx + dw - 10, roof + params["max_thickness"] * unit * 0.6, "пласт", layout.small * 0.8, "#0F1419", True, "end")
    text(ctx, dx + 10, dy + layout.small * 0.9, "глубина ↓", layout.small * 0.72, "#0F1419", True)
    share = max(0.0, min(1.0, state["trace"]))
    wx = dx + share * dw
    polyline(ctx, [(wx, dy), (wx, dy + dh)], style["measurement"]["color"], 4)
    sx, sy, sw, sh = seismic
    start, end = window(params)

    def at_time(moment: float) -> float:
        return sy + (moment - start) / (end - start) * sh

    text(ctx, sx, sy - 8, "время ↓", layout.small * 0.72, style["muted"])
    alpha = max(0.0, min(1.0, state["seismic"]))
    if alpha > 0.01:
        spacing = sw / TRACES
        gain = spacing * 0.95 / _loudest(params)
        for i in range(TRACES):
            middle = (i + 0.5) / TRACES
            _wiggle(ctx, sx + middle * sw, trace(params, _thickness(params, middle), 120), at_time, gain, style, 2, alpha)
        wedge_base = [(sx, at_time(0)), (sx + sw, at_time(2 * params["max_thickness"] / params["layer_v"]))]
        if state["tuning"] > 0.01:
            for limit, label in ((tuning(params), "настройка"), (detection(params), "порог шума")):
                lx = sx + limit / params["max_thickness"] * sw
                polyline(ctx, [(lx, sy), (lx, sy + sh)], style["uncertainty"]["color"], 3, state["tuning"], (10, 8))
                text(ctx, lx + 6, sy + sh - 8, label, layout.small * 0.68, style["uncertainty"]["color"], True, "start", state["tuning"])
        if state["naive"] > 0.01:
            polyline(ctx, [(sx, at_time(0)), (sx + sw, at_time(0))], style["uncertainty"]["color"], 4, state["naive"], (12, 8))
            polyline(ctx, wedge_base, style["uncertainty"]["color"], 4, state["naive"], (12, 8))
            text(ctx, sx + sw / 2, sy + layout.small, "ложное ожидание: как на фотографии", layout.small * 0.72, style["uncertainty"]["color"], True, "middle", state["naive"])
    polyline(ctx, [(sx + share * sw, sy), (sx + share * sw, sy + sh)], style["measurement"]["color"], 3, 0.8, (6, 6))
    rule = "нормальная" if params["polarity"] == "normal" else "обратная"
    text(ctx, sx, sy + sh + layout.small * 0.95, f"полярность {rule}, SEG: рост импеданса — {'закрашенный пик' if rule == 'нормальная' else 'впадина'}",
         layout.small * 0.66, style["muted"])


def _trace(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
           style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    top_y = y + layout.small * 1.8
    bottom_y = y + h - layout.small * 3.2
    start, end = window(params)

    def at_time(moment: float) -> float:
        return top_y + (moment - start) / (end - start) * (bottom_y - top_y)

    thickness = _thickness(params, state["trace"])
    axis = x + w / 2
    polyline(ctx, [(axis, top_y), (axis, bottom_y)], style["muted"], 2, 0.6)
    gain = w * 0.3 / _loudest(params)
    _wiggle(ctx, axis, trace(params, thickness), at_time, gain, style, 4, 1.0)
    delay = 2 * thickness / params["layer_v"]
    for moment in (0.0, delay):
        polyline(ctx, [(x + 8, at_time(moment)), (x + w - 8, at_time(moment))], style["lithology"][params["layer_lith"]]["color"], 3, 0.9, (8, 6))
    seen = apparent(params, thickness)
    row = bottom_y + layout.small * 1.1
    text(ctx, x + 10, row, f"толщина {thickness:.0f} м", layout.small * 0.7, style["lithology"][params["layer_lith"]]["color"], True)
    text(ctx, x + 10, row + layout.small * 0.95, f"видимая {seen:.0f} м", layout.small * 0.7, style["text"], True)


def _chart(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
           style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    left, right, top, bottom = x + w * 0.1, x + w * 0.95, y + layout.small * 2.9, y + h - layout.small * 3.6
    peak = max(a for _, a in curve(params)) * 1.9

    def at(thickness: float, value: float) -> tuple[float, float]:
        return left + (right - left) * thickness / params["max_thickness"], bottom - (bottom - top) * value / peak

    if state["tuning"] > 0.01:
        detect, tune = detection(params), tuning(params)
        zones = ((0, detect, "не видна"), (detect, tune, "видна по амплитуде"), (tune, params["max_thickness"], "разрешается"))
        for number, (a, b, label) in enumerate(zones):
            x1, x2 = at(a, 0)[0], at(b, 0)[0]
            fill_rect(ctx, x1, top, x2 - x1, bottom - top, style["uncertainty"]["color"], (0.05 + 0.07 * number) * state["tuning"])
            text(ctx, x1 + 6, top + layout.small * (0.8 + 0.75 * number), label, layout.small * 0.62, style["text"], False, "start", state["tuning"])
        for value, label in ((tune, "настройка"), (wavelength(params) / 4, "λ/4")):
            px = at(value, 0)[0]
            polyline(ctx, [(px, top), (px, bottom)], style["text"], 3, state["tuning"], (8, 6) if label == "λ/4" else ())
            text(ctx, px + 6, bottom - 10 - (label == "λ/4") * layout.small * 0.8, label, layout.small * 0.66, style["text"], True, "start", state["tuning"])
        noise_y = at(0, params["noise"])[1]
        polyline(ctx, [(left, noise_y), (right, noise_y)], style["uncertainty"]["color"], 3, state["tuning"], (6, 6))
        text(ctx, right - 4, noise_y - 8, "шум", layout.small * 0.62, style["uncertainty"]["color"], True, "end", state["tuning"])
    polyline(ctx, [(left, top), (left, bottom), (right, bottom)], style["muted"], 3)
    text(ctx, right, bottom + layout.small * 1.0, "толщина →", layout.small * 0.72, style["muted"], False, "end")
    text(ctx, left, top - 10, "амплитуда ↑", layout.small * 0.72, style["muted"])
    one = at(0, 1)[1]
    polyline(ctx, [(left, one), (right, one)], style["muted"], 2, 0.6, (4, 6))
    if state["naive"] > 0.01:
        polyline(ctx, [(left, one), (right, one)], style["uncertainty"]["color"], 5, state["naive"], (14, 8))
    thickness = _thickness(params, state["trace"])
    shown = [at(hh, a) for hh, a in curve(params) if hh >= thickness - 1e-9]
    color = style["measurement"]["color"]
    if len(shown) > 1:
        polyline(ctx, shown, color, 6)
    dot(ctx, *at(thickness, amplitude(params, thickness)), 11, color)
    row = bottom + layout.small * 2.0
    text(ctx, left, row, f"длина волны в пласте {wavelength(params):.0f} м", layout.small * 0.7, style["text"])
    text(ctx, left, row + layout.small * 0.95, "1 — отражение от одной границы", layout.small * 0.66, style["muted"])


def _true_scale(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], alpha: float, style: Mapping[str, Any], layout: Any) -> None:
    """Клин без вертикального преувеличения: толщина и длина в одних метрах."""
    x, y, w, h = box
    fill_rect(ctx, x, y, w, h, style["background"], 0.95 * alpha, 14)
    length = w - 40
    thick = max(1.5, params["max_thickness"] * length / params["width"])
    floor = y + h * 0.5
    fill_rect(ctx, x + 20, floor - h * 0.12, length, h * 0.24, style["lithology"][params["host_lith"]]["color"], alpha * 0.8)
    polygon(ctx, [(x + 20, floor), (x + 20 + length, floor), (x + 20 + length, floor + thick)], style["lithology"][params["layer_lith"]]["color"], alpha)
    text(ctx, x + w / 2, y + h * 0.2, "истинный масштаб", layout.small, style["text"], True, "middle", alpha)
    text(ctx, x + w / 2, y + h * 0.8, "толщина и длина в одних метрах", layout.small * 0.85, style["muted"], False, "middle", alpha)
