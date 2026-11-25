"""Дельта во времени: разрез, фации, линии времени и кривая ГК/ПС в скважине считаются из одной модели наращивания склона."""

import json
import math
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import cairo

from glava.sdk.video import LAYOUTS, dot, fill_rect, polygon, polyline, text

SUMMARY = """delta_progradation — дельта выдвигается в бассейн (проградация). Модель: профиль дельты — плоская дельтовая равнина на уровне моря, склон-клиноформа длиной front и плоское дно на глубине depth; за каждый шаг времени к профилю добавляется ровно supply/шаг площади осадка (баланс массы), поэтому берег сдвигается в море. Фация каждой порции осадка задаётся глубиной воды в момент отложения: на равнине — песок дельтовых рукавов, мельче bar_depth — песок устьевого бара, до prodelta_depth — авандельта (переслаивание), глубже — глины продельты. Отсюда разрез, линии времени (наклонные клиноформы) и кривая ГК или ПС в скважине: вверх по разрезу зерно крупнее (огрубление вверх, форма «воронки»). params: {"sea":[[время 0..1, уровень м], … по возрастанию],"supply":м² осадка на единицу ширины за весь показ,"depth":м глубина дна бассейна ниже начального уровня,"front":м длина склона по горизонтали,"width":м длина разреза,"start":м где берег в начале,"bar_depth":м,"prodelta_depth":м,"well":0..1 доля длины разреза, где скважина,"curve":"GR|SP","filtrate":"fresh|salt"}. Размыв не считается; уровень моря может расти (появляется надводная часть с рукавами) или стоять. Числа условные, если их нет в утверждениях. Действия: time 0..1 (только вперёд), facies 0..1 (подписи фаций), lines 0..1 (линии времени — бывшие поверхности склона), well 0..1 (скважина и кривая), naive 0..1 (пунктир ложного ожидания: слои горизонтальны, каждый — одно время), focus 0 нет, 1 разрез, 2 кривая, true_scale 0..1 (разрез в истинном масштабе)."""
STATE_MODEL = "профиль дельты с балансом площади осадка за шаг; фация порции — по глубине воды при отложении; разрез, линии времени и кривая ГК/ПС из одной истории"
FITS = ("дельт", "проград|выдвиг|наступ", "устьев|бар\\b|рукав", "продельт|авандельт", "огрублен|укрупнен|воронк|крупнее", "фаци")
ACTIONS = {"time", "facies", "lines", "well", "naive", "focus", "true_scale"}
FACIES = ("channel", "bar", "front", "prodelta")
NAMES = {"channel": "дельтовый рукав", "bar": "устьевой бар", "front": "авандельта", "prodelta": "продельта"}
CLAY = {"channel": 0.0, "bar": 0.12, "front": 0.5, "prodelta": 0.95}
COLUMNS = 150
STEPS = 120
LINES_EVERY = 12
PLAIN = 0.3


def sea_level(params: Mapping[str, Any], t: float) -> float:
    points = params["sea"]
    for (t1, v1), (t2, v2) in zip(points, points[1:], strict=False):
        if t <= t2:
            return v1 + (v2 - v1) * max(0.0, t - t1) / (t2 - t1)
    return points[-1][1]


def profile(params: Mapping[str, Any], shore: float, sea: float, x: float) -> float:
    """Отметка поверхности дельты (м, вверх положительно) при береге shore: равнина, склон-сигмоида, дно."""
    if x <= shore:
        return sea
    share = (x - shore) / params["front"]
    if share >= 1:
        return -params["depth"]
    return sea - (sea + params["depth"]) * (1 - math.cos(math.pi * share)) / 2


def facies_at(params: Mapping[str, Any], water: float) -> str:
    """Фация по глубине воды при отложении."""
    if water <= PLAIN:
        return "channel"
    if water <= params["bar_depth"]:
        return "bar"
    return "front" if water <= params["prodelta_depth"] else "prodelta"


def _grid(params: Mapping[str, Any]) -> list[float]:
    return [params["width"] * (i + 0.5) / COLUMNS for i in range(COLUMNS)]


@lru_cache(maxsize=16)
def _history_of(key: str) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...], tuple[tuple[tuple[int, float, float, str], ...], ...]]:
    """Берег по шагам, поверхности по шагам, порции осадка по колонкам: (шаг, низ, верх, фация)."""
    params = json.loads(key)
    xs = _grid(params)
    cell = params["width"] / COLUMNS
    shore = params["start"]
    surface = [profile(params, shore, sea_level(params, 0), x) for x in xs]
    shores, surfaces, parts = [shore], [tuple(surface)], [[] for _ in xs]
    portion = params["supply"] / STEPS
    for step in range(1, STEPS + 1):
        sea = sea_level(params, step / STEPS)

        def added(position: float, sea: float = sea) -> float:
            return sum(max(0.0, profile(params, position, sea, x) - z) for x, z in zip(xs, surface, strict=True)) * cell

        low, high = shore - params["front"], params["width"] * 2
        for _ in range(60):
            middle = (low + high) / 2
            low, high = (middle, high) if added(middle) < portion else (low, middle)
        shore = high
        for i, x in enumerate(xs):
            top = profile(params, shore, sea, x)
            if top > surface[i] + 1e-9:
                parts[i].append((step, surface[i], top, facies_at(params, sea - (surface[i] + top) / 2)))
                surface[i] = top
        shores.append(shore)
        surfaces.append(tuple(surface))
    return tuple(shores), tuple(surfaces), tuple(tuple(p) for p in parts)


def history(params: Mapping[str, Any]) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...], tuple[tuple[tuple[int, float, float, str], ...], ...]]:
    return _history_of(json.dumps(dict(params), sort_keys=True))


def shoreline(params: Mapping[str, Any], t: float) -> float:
    return history(params)[0][round(max(0.0, min(1.0, t)) * STEPS)]


def deposited(params: Mapping[str, Any], t: float) -> float:
    """Площадь осадка (м²) к моменту t: проверка баланса."""
    step = round(max(0.0, min(1.0, t)) * STEPS)
    cell = params["width"] / COLUMNS
    return sum(top - bottom for column in history(params)[2] for s, bottom, top, _ in column if s <= step) * cell


def column_at(params: Mapping[str, Any], share: float, t: float) -> list[tuple[float, float, str]]:
    """Порции осадка в колонке скважины снизу вверх к моменту t: (низ, верх, фация)."""
    step = round(max(0.0, min(1.0, t)) * STEPS)
    index = min(COLUMNS - 1, max(0, int(share * COLUMNS)))
    return [(bottom, top, kind) for s, bottom, top, kind in history(params)[2][index] if s <= step]


def log_curve(params: Mapping[str, Any], share: float, t: float, samples: int = 120) -> list[tuple[float, float]]:
    """Кривая ГК/ПС в скважине: (глубина от поверхности м, глинистость 0..1), сглаженная окном прибора в треть метра на шаг."""
    parts = column_at(params, share, t)
    if not parts:
        return []
    roof, floor = parts[-1][1], parts[0][0]
    depths = [(roof - floor) * i / (samples - 1) for i in range(samples)]

    def clay(depth: float) -> float:
        level = roof - depth
        return next((CLAY[kind] for bottom, top, kind in parts if bottom - 1e-9 <= level <= top + 1e-9), CLAY["prodelta"])

    raw = [clay(d) for d in depths]
    blur = 4
    return [(d, sum(raw[max(0, i - blur): i + blur + 1]) / len(raw[max(0, i - blur): i + blur + 1])) for i, d in enumerate(depths)]


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    need = ("sea", "supply", "depth", "front", "width", "start", "bar_depth", "prodelta_depth", "well", "curve")
    missing = [k for k in need if k not in params]
    if missing:
        return [f"нет параметров: {', '.join(missing)}"]
    sea = params["sea"]
    if len(sea) < 2 or sea[0][0] != 0 or sea[-1][0] != 1 or any(b[0] <= a[0] for a, b in zip(sea, sea[1:], strict=False)):
        return ["sea: время идёт от 0 до 1 по возрастанию"]
    issues = [f"{k} должен быть больше нуля" for k in ("supply", "depth", "front", "width", "start", "bar_depth", "prodelta_depth") if params[k] <= 0]
    if issues:
        return issues
    if not PLAIN < params["bar_depth"] < params["prodelta_depth"] < params["depth"]:
        issues.append("глубины по порядку: bar_depth < prodelta_depth < depth")
    if params["front"] < params["width"] / 25:
        issues.append("склон слишком короткий: front не меньше width/25")
    if any(v < sea[0][1] - 1e-9 for _, v in sea) or any(v - sea[0][1] > params["depth"] * 0.5 for _, v in sea):
        issues.append("уровень моря не ниже начального (размыв не считается) и растёт не больше чем на половину глубины")
    if params["start"] + params["front"] > params["width"] * 0.6:
        issues.append("в начале дельта уже у края: start + front не больше 0.6 width")
    if params["curve"] not in ("GR", "SP") or params.get("filtrate", "fresh") not in ("fresh", "salt"):
        issues.append("curve: GR или SP; filtrate: fresh или salt")
    if not 0 < params["well"] < 1:
        issues.append("well от 0 до 1")
    if issues:
        return issues
    end = shoreline(params, 1)
    if end + params["front"] > params["width"] * 1.02:
        issues.append("дельта уходит за край разреза: уменьшите supply или увеличьте width")
    if end < params["start"] + params["front"] * 0.5:
        issues.append("дельта почти не выдвигается: увеличьте supply")
    if not params["start"] < params["well"] * params["width"] < end:
        issues.append("скважина должна стоять там, куда берег дойдёт к концу: между start и концом проградации")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    times = [b["action"]["time"] for b in beats if "time" in b["action"]]
    if any(b < a for a, b in zip(times, times[1:], strict=False)) or any(not 0 <= v <= 1 for v in times):
        issues.append("time идёт только вперёд, от 0 до 1")
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"time": 0.0, "facies": 0.0, "lines": 0.0, "well": 0.0, "naive": 0.0, "focus": 0.0, "true_scale": 0.0}


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    x, y, w, h = area
    gap = layout.small * 0.5
    if layout.height > layout.width:
        return [(x, y, w, h * 0.56 - gap), (x, y + h * 0.56, w, h * 0.44)]
    return [(x, y, w * 0.7 - gap, h), (x + w * 0.7, y, w * 0.3, h)]


def _limits(params: Mapping[str, Any]) -> tuple[float, float]:
    high = max(v for _, v in params["sea"])
    return -params["depth"] * 1.12, high + (high + params["depth"]) * 0.3


def _inner(box: tuple[float, float, float, float], layout: Any) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return x + 10, y + layout.small * 1.7, w - 20, h - layout.small * 4.2


def plaque(params: Mapping[str, Any], kind: str) -> str:
    """Вертикальное преувеличение разреза: из тех же размеров, что и рисунок."""
    layout = LAYOUTS[kind]
    _, _, w, h = _inner(_boxes(layout.scene, layout)[0], layout)
    low, high = _limits(params)
    factor = round((h / (high - low)) / (w / params["width"]))
    word = "раза" if factor % 10 in (2, 3, 4) and factor % 100 not in (12, 13, 14) else "раз"
    return f"толщины увеличены в {factor} {word}"


def _color(style: Mapping[str, Any], clay: float) -> str:
    """Цвет порции: смесь цветов песчаника и глины из легенды по доле глины."""
    sand, shale = style["lithology"]["sand"]["color"], style["lithology"]["shale"]["color"]
    mix = [round(int(sand[i:i + 2], 16) * (1 - clay) + int(shale[i:i + 2], 16) * clay) for i in (1, 3, 5)]
    return "#" + "".join(f"{v:02X}" for v in mix)


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    now = max(0.0, min(1.0, state["time"]))
    boxes = _boxes(area, layout)
    titles = ("разрез дельты", "ГК в скважине" if params["curve"] == "GR" else "ПС в скважине")
    for number, (box, title, painter) in enumerate(zip(boxes, titles, (_section, _log), strict=True), start=1):
        x, y, w, h = box
        fill_rect(ctx, x, y, w, h, style["panel"], radius=14)
        text(ctx, x + layout.small * 0.5, y + layout.small * 1.1, title, layout.small * 0.85, style["muted"], True)
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
    x, y, w, h = _inner(box, layout)
    low, high = _limits(params)
    shores, surfaces, parts = history(params)
    step = round(now * STEPS)
    cell = w / COLUMNS

    def at(level: float) -> float:
        return y + (high - level) / (high - low) * h

    sea = sea_level(params, now)
    fill_rect(ctx, x, at(sea), w, at(low) - at(sea), style["fluids"]["water"]["color"], 0.3)
    polyline(ctx, [(x, at(sea)), (x + w, at(sea))], style["fluids"]["water"]["color"], 4)
    text(ctx, x + w - 8, at(sea) - 10, "уровень моря", layout.small * 0.72, style["fluids"]["water"]["color"], True, "end")
    base = surfaces[0]
    old = [(x + (i + 0.5) * cell, at(z)) for i, z in enumerate(base)]
    polygon(ctx, [(x, at(low)), *old, (x + w, at(low))], style["muted"], 0.55)
    text(ctx, x + 10, at(low) - 10, "основание", layout.small * 0.66, "#0F1419", True)
    for i, column in enumerate(parts):
        left = round(x + i * cell)
        right = round(x + (i + 1) * cell)
        for bottom, top, kind in _chunks(column, step):
            fill_rect(ctx, left, at(top), right - left, at(bottom) - at(top), _color(style, CLAY[kind]))
    if state["lines"] > 0.01:
        for k in range(LINES_EVERY, step + 1, LINES_EVERY):
            points = [(x + (i + 0.5) * cell, at(z)) for i, z in enumerate(surfaces[k])]
            polyline(ctx, points, "#0F1419", 2, 0.7 * state["lines"])
    if state["naive"] > 0.01:
        top_now = max(surfaces[step])
        for k in range(1, 6):
            level = low + (top_now - low) * k / 6
            polyline(ctx, [(x, at(level)), (x + w, at(level))], style["uncertainty"]["color"], 3, state["naive"], (12, 8))
        text(ctx, x + w / 2, at(low) - layout.small * 0.5, "ложное ожидание: слой = одно время", layout.small * 0.75, style["uncertainty"]["color"], True, "middle", state["naive"])
    shore_x = x + shores[step] / params["width"] * w
    dot(ctx, shore_x, at(sea), 9, style["text"])
    text(ctx, shore_x + 14, at(sea) + layout.small * 0.95, "берег", layout.small * 0.7, style["text"], True)
    if state["facies"] > 0.01 and step > 0:
        _labels(ctx, (x, y, w, h), params, step, at, state["facies"], style, layout)
    if state["well"] > 0.01:
        wx = x + params["well"] * w
        polyline(ctx, [(wx, y), (wx, at(low))], style["measurement"]["color"], 6, state["well"])
    text(ctx, x, y + h + layout.small * 1.0, "море →", layout.small * 0.72, style["muted"], False, "start")
    text(ctx, x + w, y + h + layout.small * 1.0, "цвет: доля глины, светлее — песок", layout.small * 0.66, style["muted"], False, "end")


def _chunks(column: Sequence[tuple[int, float, float, str]], step: int) -> list[list[Any]]:
    """Порции одной колонки до шага step, соседние одной фации слиты: [низ, верх, фация]."""
    chunks: list[list[Any]] = []
    for s, bottom, top, kind in column:
        if s > step:
            break
        if chunks and chunks[-1][2] == kind and abs(chunks[-1][1] - bottom) < 1e-6:
            chunks[-1][1] = top
        else:
            chunks.append([bottom, top, kind])
    return chunks


def _labels(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], step: int, at: Any, alpha: float,
            style: Mapping[str, Any], layout: Any) -> None:
    """Подписи фаций в одной колонке, которую склон уже прошёл; подписи не налезают друг на друга."""
    x, _, w, _ = box
    shores, _, parts = history(params)
    target = max(params["start"], shores[step] - params["front"] * 0.6)
    index = min(COLUMNS - 1, int(target / params["width"] * COLUMNS))
    cx = x + (index + 0.5) / COLUMNS * w
    last = -1e9
    for bottom, top, kind in reversed(_chunks(parts[index], step)):
        y = max(at((top + bottom) / 2) + layout.small * 0.3, last + layout.small * 0.85)
        if kind == "channel":
            y = at(top) - layout.small * 0.35
        text(ctx, cx, y, NAMES[kind], layout.small * 0.7, style["text"] if kind == "channel" else "#0F1419", True, "middle", alpha)
        last = y


def _log(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], now: float,
         style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    top, bottom = y + layout.small * 2.6, y + h - layout.small * 3.2
    column_w = w * 0.3
    track_l, track_r = x + column_w + 30, x + w - 16
    text(ctx, x + 12, y + layout.small * 2.2, "глубина ↓", layout.small * 0.68, style["muted"])
    parts = column_at(params, params["well"], now)
    if not parts:
        text(ctx, x + w / 2, (top + bottom) / 2, "дельта сюда ещё не дошла", layout.small * 0.72, style["muted"], False, "middle")
        return
    full = column_at(params, params["well"], 1.0)
    span = full[-1][1] - full[0][0]
    roof = parts[-1][1]

    def at(level: float) -> float:
        return top + (roof - level) / span * (bottom - top)

    index = min(COLUMNS - 1, max(0, int(params["well"] * COLUMNS)))
    for bottom_m, top_m, kind in _chunks(history(params)[2][index], round(now * STEPS)):
        fill_rect(ctx, x + 12, at(top_m), column_w, at(bottom_m) - at(top_m), _color(style, CLAY[kind]))
    if state["well"] < 0.01:
        return
    key = "GR" if params["curve"] == "GR" else "SP"
    color = style["curves"][key]["color"]
    sign = 1 if key == "GR" or params.get("filtrate", "fresh") == "fresh" else -1
    points = [(track_l + (track_r - track_l) * (value if sign > 0 else 1 - value), at(roof - depth)) for depth, value in log_curve(params, params["well"], now)]
    polyline(ctx, [(track_l, top), (track_l, bottom)], style["muted"], 2, 0.5)
    polyline(ctx, points, color, 6, state["well"])
    note = "ГК: рост вправо" if key == "GR" else ("ПС: песок — влево" if sign > 0 else "ПС: песок — вправо")
    text(ctx, x + 12, bottom + layout.small * 1.1, note, layout.small * 0.68, color, True, "start", state["well"])
    text(ctx, x + 12, bottom + layout.small * 2.0, "вверх зерно крупнее", layout.small * 0.68, style["text"], False, "start", state["well"])


def _true_scale(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], now: float, alpha: float, style: Mapping[str, Any], layout: Any) -> None:
    """Разрез без вертикального преувеличения: высота и длина в одних метрах."""
    x, y, w, h = box
    fill_rect(ctx, x, y, w, h, style["background"], 0.95 * alpha, 14)
    scale = (w - 40) / params["width"]
    floor = y + h * 0.55
    surface = history(params)[1][round(now * STEPS)]
    points = [(x + 20 + (i + 0.5) / COLUMNS * (w - 40), floor - (z + params["depth"]) * scale) for i, z in enumerate(surface)]
    polygon(ctx, [(x + 20, floor), *points, (x + w - 20, floor)], style["lithology"]["sand"]["color"], alpha)
    polyline(ctx, [(x + 20, floor - (sea_level(params, now) + params["depth"]) * scale), (x + w - 20, floor - (sea_level(params, now) + params["depth"]) * scale)],
             style["fluids"]["water"]["color"], 2, alpha)
    text(ctx, x + w / 2, y + h * 0.25, "истинный масштаб", layout.small, style["text"], True, "middle", alpha)
    text(ctx, x + w / 2, y + h * 0.75, "дельта — тонкий плоский клин", layout.small * 0.85, style["muted"], False, "middle", alpha)
