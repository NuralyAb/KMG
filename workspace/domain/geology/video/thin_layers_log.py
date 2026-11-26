"""Тонкие прослои и зонд: кривая сопротивления, глинистость пачки и эффективная толщина считаются из одной модели слоёв и окна прибора."""

import math
from collections.abc import Mapping, Sequence
from typing import Any

import cairo

from glava.sdk.video import LAYOUTS, dot, fill_rect, polyline, text

SUMMARY = """thin_layers_log — пачка тонких прослоев коллектора и глины между вмещающими глинами; прибор сопротивления едет снизу вверх и видит не точку, а окно длиной window: в окне проводимости прослоев складываются с весами по толщине (ток идёт вдоль напластования), кажущееся сопротивление — обратная величина. Поэтому кривая сглаживает прослои тоньше окна и в пачке стоит на среднем значении ρп; по нему из того же уравнения находят долю глины пачки и эффективную толщину h·(1 − доля глины). Микрозонд с малым окном window_fine прослои различает. params: {"layers":[сверху вниз {"lith":"shale|sand|limestone|dolomite","h":м,"fluid":"oil|gas|water" или null (только у коллектора)}] — первый и последний слой глина (вмещающие), между ними пачка,"rho_res":Ом·м прослоя коллектора,"rho_shale":Ом·м глины,"window":м окно основного зонда,"window_fine":м окно микрозонда}. 3–14 слоёв. Числа условные, если их нет в утверждениях: тогда их не произносят. Действия: tool 0..1 (прибор едет снизу вверх и пишет кривую), fine 0..1 (кривая микрозонда), naive 0..1 (пунктир ложного ожидания: кривая повторяет каждый прослой), pack 0..1 (расчёт: ρп по кривой, доля глины, эффективная толщина), focus 0 нет, 1 колонка, 2 кривые, 3 расчёт, true_scale 0..1 (ствол и зонд в истинном масштабе)."""
STATE_MODEL = "слои с сопротивлением; прибор усредняет проводимость в окне по толщине; кривая, ρ пачки, доля глины и эффективная толщина из одной функции"
FITS = ("тонк|прослой|пропласт|переслаив", "пачк", "сопротивлен", "глинист", "эффективн\\w* толщин", "разрешающ|окн[оа] зонда|зонд")
ACTIONS = {"tool", "fine", "naive", "pack", "focus", "true_scale"}
RESERVOIRS = {"sand", "limestone", "dolomite"}
BIT_M = 0.216
SAMPLES = 400


def resistivity(params: Mapping[str, Any], layer: Mapping[str, Any]) -> float:
    return params["rho_shale"] if layer["lith"] == "shale" else params["rho_res"]


def edges(params: Mapping[str, Any]) -> list[float]:
    """Глубины границ слоёв от кровли первого слоя, м."""
    out = [0.0]
    for layer in params["layers"]:
        out.append(out[-1] + layer["h"])
    return out


def _cumulative(params: Mapping[str, Any], depth: float) -> float:
    """Интеграл проводимости от кровли до depth; за пределами разреза продолжаются крайние слои."""
    bounds, layers = edges(params), params["layers"]
    if depth <= 0:
        return depth / resistivity(params, layers[0])
    total = 0.0
    for (top, bottom), layer in zip(zip(bounds, bounds[1:], strict=False), layers, strict=True):
        if depth <= bottom:
            return total + (depth - top) / resistivity(params, layer)
        total += (bottom - top) / resistivity(params, layer)
    return total + (depth - bounds[-1]) / resistivity(params, layers[-1])


def true_value(params: Mapping[str, Any], depth: float) -> float:
    bounds = edges(params)
    index = next((i for i, b in enumerate(bounds[1:]) if depth < b), len(params["layers"]) - 1)
    return resistivity(params, params["layers"][index])


def apparent(params: Mapping[str, Any], depth: float, window: float) -> float:
    """Кажущееся сопротивление: проводимость, усреднённая по окну зонда с весами по толщине, и обратная величина."""
    if window <= 0:
        return true_value(params, depth)
    conductance = (_cumulative(params, depth + window / 2) - _cumulative(params, depth - window / 2)) / window
    return 1 / conductance


def pack(params: Mapping[str, Any]) -> tuple[float, float]:
    """Кровля и подошва пачки (между вмещающими глинами)."""
    bounds = edges(params)
    return bounds[1], bounds[-2]


def pack_shale_share(params: Mapping[str, Any]) -> float:
    """Доля глины в пачке по толщинам прослоев — истинная."""
    inner = params["layers"][1:-1]
    return sum(x["h"] for x in inner if x["lith"] == "shale") / sum(x["h"] for x in inner)


def pack_resistivity(params: Mapping[str, Any], share: float) -> float:
    """Уравнение пачки: обратное сопротивление — сумма долей, делённых на сопротивления прослоев."""
    return 1 / (share / params["rho_shale"] + (1 - share) / params["rho_res"])


def share_from(params: Mapping[str, Any], rho: float) -> float:
    """Доля глины из сопротивления пачки — то же уравнение, решённое относительно доли."""
    return (1 / rho - 1 / params["rho_res"]) / (1 / params["rho_shale"] - 1 / params["rho_res"])


def reading(params: Mapping[str, Any]) -> float:
    """ρп по диаграмме: среднее по проводимости показание основного зонда в середине пачки, вдали от её границ."""
    top, bottom = pack(params)
    margin = min(params["window"] / 2, (bottom - top) / 4)
    depths = [top + margin + (bottom - top - 2 * margin) * i / 40 for i in range(41)]
    return 1 / (sum(1 / apparent(params, d, params["window"]) for d in depths) / len(depths))


def effective(params: Mapping[str, Any], share: float) -> float:
    top, bottom = pack(params)
    return (bottom - top) * (1 - share)


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    need = ("layers", "rho_res", "rho_shale", "window", "window_fine")
    missing = [k for k in need if k not in params]
    if missing:
        return [f"нет параметров: {', '.join(missing)}"]
    layers = params["layers"]
    if not 3 <= len(layers) <= 14:
        return ["нужно 3–14 слоёв: вмещающая глина, пачка, вмещающая глина"]
    issues = [f"{k} должен быть больше нуля" for k in ("rho_res", "rho_shale", "window", "window_fine") if params[k] <= 0]
    issues += ["толщина слоя больше нуля" for x in layers if x.get("h", 0) <= 0][:1]
    issues += ["литология: shale, sand, limestone, dolomite" for x in layers if x.get("lith") not in RESERVOIRS | {"shale"}][:1]
    if issues:
        return issues
    issues += [f"флюид только в коллекторе (слой {i + 1})" for i, x in enumerate(layers) if x.get("fluid") and x["lith"] == "shale"]
    issues += [f"флюид: oil, gas или water (слой {i + 1})" for i, x in enumerate(layers) if x.get("fluid") not in (None, "oil", "gas", "water")]
    if layers[0]["lith"] != "shale" or layers[-1]["lith"] != "shale":
        issues.append("первый и последний слой — вмещающая глина")
    elif min(layers[0]["h"], layers[-1]["h"]) < params["window"]:
        issues.append("вмещающие глины толще окна зонда, иначе кривая не дойдёт до их сопротивления")
    inner = layers[1:-1]
    if not any(x["lith"] == "shale" for x in inner) or not any(x["lith"] != "shale" for x in inner):
        issues.append("в пачке нужны и прослои коллектора, и прослои глины")
    if not any(x["h"] < params["window"] for x in inner):
        issues.append("в пачке нет прослоя тоньше окна зонда: сглаживать нечего")
    if sum(x["h"] for x in inner) < 2 * params["window"]:
        issues.append("пачка тоньше двух окон зонда: ρп по кривой не прочитать")
    if not params["window_fine"] < min(x["h"] for x in inner):
        issues.append("окно микрозонда должно быть тоньше самого тонкого прослоя пачки")
    ratio = params["rho_res"] / params["rho_shale"]
    if 0.7 < ratio < 1.4:
        issues.append("сопротивления коллектора и глины почти равны: долю глины по ним не найти")
    fluids = [x.get("fluid") for x in inner if x.get("fluid")]
    order = ("gas", "oil", "water")
    if any(order.index(b) < order.index(a) for a, b in zip(fluids, fluids[1:], strict=False)):
        issues.append("газ над нефтью, нефть над водой")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    issues += ["tool от 0 до 1" for b in beats if not 0 <= b["action"].get("tool", 0) <= 1][:1]
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"tool": 0.0, "fine": 0.0, "naive": 0.0, "pack": 0.0, "focus": 0.0, "true_scale": 0.0}


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    """Колонка, кривые, расчёт: в шортсе колонка и кривые сверху, расчёт снизу."""
    x, y, w, h = area
    gap = layout.small * 0.5
    if layout.height > layout.width:
        top_h = h * 0.64
        side = w * 0.36
        return [(x, y, side, top_h - gap), (x + side + gap, y, w - side - gap, top_h - gap), (x, y + top_h, w, h - top_h)]
    first, second = w * 0.22, w * 0.4
    return [(x, y, first, h), (x + first + gap, y, second, h), (x + first + second + 2 * gap, y, w - first - second - 2 * gap, h)]


def _depth_span(box: tuple[float, float, float, float], layout: Any) -> tuple[float, float]:
    _, y, _, h = box
    return y + layout.small * 2.4, y + h - layout.small * 2.2


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Ширина ствола на колонке против истинной при том же масштабе глубин."""
    layout = LAYOUTS[kind]
    box = _boxes(layout.scene, layout)[0]
    top, bottom = _depth_span(box, layout)
    per_metre = (bottom - top) / edges(params)[-1]
    factor = round(_bore_width(box) / (BIT_M * per_metre))
    word = "раза" if factor % 10 in (2, 3, 4) and factor % 100 not in (12, 13, 14) else "раз"
    return f"глубина в масштабе, ширина ствола увеличена в {factor} {word}"


def _bore_width(box: tuple[float, float, float, float]) -> float:
    return box[2] * 0.16


def _tool_depth(params: Mapping[str, Any], share: float) -> float:
    return edges(params)[-1] * (1 - max(0.0, min(1.0, share)))


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    boxes = _boxes(area, layout)
    titles = ("пласты и зонд", "сопротивление", "пачка по кривой")
    for number, (box, title, painter) in enumerate(zip(boxes, titles, (_column, _curves, _pack), strict=True), start=1):
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
        _true_scale(ctx, boxes[0], params, state, style, layout)


def _column(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
            style: Mapping[str, Any], layout: Any) -> None:
    x, _, w, _ = box
    top, bottom = _depth_span(box, layout)
    total = edges(params)[-1]

    def at(depth: float) -> float:
        return top + depth / total * (bottom - top)

    bounds = edges(params)
    left, right = x + w * 0.22, x + w - 12
    for (a, b), layer in zip(zip(bounds, bounds[1:], strict=False), params["layers"], strict=True):
        fill_rect(ctx, left, at(a), right - left, at(b) - at(a), style["lithology"][layer["lith"]]["color"])
        if layer.get("fluid"):
            fill_rect(ctx, right - 14, at(a), 14, at(b) - at(a), style["fluids"][layer["fluid"]]["color"])
        polyline(ctx, [(left, at(a)), (right, at(a))], style["panel"], 1)
    step = _tick(total)
    for k in range(int(total / step) + 1):
        depth = k * step
        polyline(ctx, [(left - 10, at(depth)), (left, at(depth))], style["muted"], 2)
        text(ctx, left - 14, at(depth) + layout.small * 0.25, f"{depth:g}", layout.small * 0.62, style["muted"], False, "end")
    text(ctx, x + 10, top - layout.small * 0.5, "глубина, м ↓", layout.small * 0.66, style["muted"])
    bore = _bore_width(box)
    axis = (left + right) / 2
    fill_rect(ctx, axis - bore / 2, top, bore, bottom - top, style["fluids"]["mud"]["color"], 0.85)
    depth = _tool_depth(params, state["tool"])
    half = params["window"] / 2
    fill_rect(ctx, axis - bore * 0.3, at(depth - half), bore * 0.6, at(depth + half) - at(depth - half), style["measurement"]["color"], 0.9)
    dot(ctx, axis, at(depth), bore * 0.22, "#0F1419")


def _tick(total: float) -> float:
    raw = total / 6
    power = 10 ** math.floor(math.log10(raw))
    return next(m * power for m in (1, 2, 5, 10) if m * power >= raw)


def _curves(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
            style: Mapping[str, Any], layout: Any) -> None:
    x, _, w, _ = box
    top, bottom = _depth_span(box, layout)
    total = edges(params)[-1]
    low = min(params["rho_res"], params["rho_shale"]) / 1.6
    high = max(params["rho_res"], params["rho_shale"]) * 1.6
    left, right = x + 16, x + w - 16

    def at(depth: float, rho: float) -> tuple[float, float]:
        return left + (right - left) * math.log(rho / low) / math.log(high / low), top + depth / total * (bottom - top)

    marks = [m * 10 ** d for d in range(math.floor(math.log10(low)), math.ceil(math.log10(high)) + 1) for m in (1, 2, 5)]
    for value in [m for m in marks if low <= m <= high]:
        gx = at(0, value)[0]
        polyline(ctx, [(gx, top), (gx, bottom)], style["muted"], 1, 0.4)
        text(ctx, gx, bottom + layout.small * 0.9, f"{value:g}", layout.small * 0.6, style["muted"], False, "middle")
    if state["pack"] > 0.01:
        roof, floor = pack(params)
        px = at(0, reading(params))[0]
        polyline(ctx, [(px, at(roof, low)[1]), (px, at(floor, low)[1])], style["text"], 3, state["pack"], (8, 6))
        polyline(ctx, [(right - 6, at(roof, low)[1]), (right, at(roof, low)[1]), (right, at(floor, low)[1]), (right - 6, at(floor, low)[1])],
                 style["text"], 3, state["pack"])
        text(ctx, right - 10, (at(roof, low)[1] + at(floor, low)[1]) / 2, "пачка", layout.small * 0.66, style["text"], True, "end", state["pack"])
    text(ctx, right, top - layout.small * 0.5, "Ом·м, лог. шкала →", layout.small * 0.62, style["muted"], False, "end")
    depths = [total * i / SAMPLES for i in range(SAMPLES + 1)]
    if state["naive"] > 0.01:
        steps = [p for d in depths for p in [at(d, true_value(params, d))]]
        polyline(ctx, steps, style["uncertainty"]["color"], 4, state["naive"], (10, 8))
        text(ctx, (left + right) / 2, top + layout.small * 0.3, "ожидание: каждый прослой", layout.small * 0.66, style["uncertainty"]["color"], True, "middle", state["naive"])
    depth = _tool_depth(params, state["tool"])
    recorded = [d for d in depths if d >= depth]
    if state["fine"] > 0.01:
        polyline(ctx, [at(d, apparent(params, d, params["window_fine"])) for d in recorded], style["curves"]["RES_SHALLOW"]["color"], 3, state["fine"])
    if len(recorded) > 1:
        polyline(ctx, [at(d, apparent(params, d, params["window"])) for d in recorded], style["curves"]["RES"]["color"], 6)
    dot(ctx, *at(depth, apparent(params, depth, params["window"])), 10, style["curves"]["RES"]["color"])
    row = bottom + layout.small * 1.9
    text(ctx, left, row, "КС: основной зонд", layout.small * 0.66, style["curves"]["RES"]["color"], True)
    if state["fine"] > 0.01:
        text(ctx, right, row, "МКЗ: микрозонд", layout.small * 0.66, style["curves"]["RES_SHALLOW"]["color"], True, "end", state["fine"])


def _pack(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
          style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, _ = box
    alpha = max(0.0, min(1.0, state["pack"]))
    size = layout.small * (0.64 if layout.height > layout.width else 0.72)
    row = y + layout.small * 2.6
    left = x + layout.small * 0.5
    top, bottom = pack(params)
    text(ctx, left, row, f"пачка {bottom - top:.1f} м между глинами", size, style["text"])
    if alpha < 0.01:
        text(ctx, left, row + layout.small * 1.2, "прослои тоньше окна зонда?", size, style["muted"])
        return
    rho = reading(params)
    estimated, true_share = share_from(params, rho), pack_shale_share(params)
    lines = [(f"ρп по кривой {rho:.1f} Ом·м", style["curves"]["RES"]["color"]),
             ("проводимости слоёв", style["muted"]),
             ("складываются по толщине", style["muted"])]
    for k, (value, color) in enumerate(lines, start=1):
        text(ctx, left, row + layout.small * 1.1 * k, value, size, color, k == 1, "start", alpha)
    two = layout.height > layout.width
    bar_left = x + w / 2 if two else left
    bar_top = row - layout.small * 0.4 if two else row + layout.small * 4.6
    bar_w = (w / 2 if two else w) - layout.small
    for k, (label, share) in enumerate((("доля глины по кривой", estimated), ("доля глины по прослоям", true_share))):
        by = bar_top + layout.small * 2.2 * k
        text(ctx, bar_left, by, f"{label}: {share * 100:.0f} %", size, style["text"], k == 0, "start", alpha)
        fill_rect(ctx, bar_left, by + 10, bar_w, layout.small * 0.6, style["lithology"]["sand"]["color"], alpha)
        fill_rect(ctx, bar_left, by + 10, bar_w * max(0.0, min(1.0, share)), layout.small * 0.6, style["lithology"]["shale"]["color"], alpha)
    text(ctx, bar_left, bar_top + layout.small * 4.6, f"эффективная толщина {effective(params, estimated):.1f} м", size * 1.05, style["text"], True, "start", alpha)


def _true_scale(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float],
                style: Mapping[str, Any], layout: Any) -> None:
    """Ствол, зонд и прослои в одном масштабе."""
    alpha = state["true_scale"]
    x, y, w, h = box
    fill_rect(ctx, x, y, w, h, style["background"], 0.95 * alpha, 14)
    top, bottom = _depth_span(box, layout)
    total = edges(params)[-1]
    per_metre = (bottom - top) / total
    bounds = edges(params)
    left, right = x + w * 0.22, x + w - 12
    for (a, b), layer in zip(zip(bounds, bounds[1:], strict=False), params["layers"], strict=True):
        fill_rect(ctx, left, top + a * per_metre, right - left, (b - a) * per_metre, style["lithology"][layer["lith"]]["color"], alpha)
    axis = (left + right) / 2
    bore = max(1.5, BIT_M * per_metre)
    fill_rect(ctx, axis - bore / 2, top, bore, bottom - top, style["fluids"]["mud"]["color"], alpha)
    depth = _tool_depth(params, state["tool"])
    fill_rect(ctx, axis - bore / 2, top + (depth - params["window"] / 2) * per_metre, bore, params["window"] * per_metre, style["measurement"]["color"], alpha)
    text(ctx, x + w / 2, y + layout.small * 1.1, "истинный масштаб", layout.small * 0.8, style["text"], True, "middle", alpha)
