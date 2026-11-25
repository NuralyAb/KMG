"""Зона проникновения во времени: пласты у скважины, показания и их история считаются из одной модели."""

import math
import random
from collections.abc import Mapping, Sequence
from typing import Any

import cairo

from glava.sdk.video import arrow, dot, fill_rect, polyline, text

SUMMARY = """invasion_zone — зона проникновения фильтрата растёт, а затем расформировывается; показания приборов считаются из неё. Разрез у скважины, показания по слоям и их история во времени. params: {"mode":"resistivity|neutron","layers":[сверху вниз 2–4 {"label":"до 14 знаков","lith":"sand|limestone|dense|shale","fluid":"gas|oil|water" или null,"perm":0..1 проницаемость (0 — фильтрат не входит),"native":показание или сопротивление неизменной части,"invaded":то же в зоне проникновения}],"probes":[1–2 {"label":"до 8 знаков","depth":0.05..1 глубинность в долях вида,"curve":"RES|RES_SHALLOW|NEUTRON"}],"depth_max":0.2..0.8 наибольшая глубина проникновения в долях вида,"cased":true|false,"contact":номер слоя, под которым показан контакт, или 0}. Для neutron native и invaded — условные показания нейтронного метода: против газа native больше. Числа условные, вслух не произносятся. Действия: invade 0..1 (фильтрат входит), dissipate 0..1 (зона расформировывается; быстрее там, где проницаемость больше и зона меньше), casing 0..1 (спущена колонна, после неё invade не растёт), tracks 0..1 (показания), history 0..1 (история во времени), contact 0..1 (линия контакта), focus 0 или номер слоя, true_scale 0..1 (подпись о масштабе)."""
STATE_MODEL = "радиус зоны проникновения в каждом слое: рост по проницаемости, расформирование со своей скоростью; показание — среднее по глубинности зонда"
FITS = ("проникновен", "расформирован", "повторн", "фильтрат", "градиент", "разноглубинн|мбк|бк-3|микро", "нейтрон")
ACTIONS = {"invade", "dissipate", "casing", "tracks", "history", "contact", "focus", "true_scale"}
ORDER = ("gas", "oil", "water")
HISTORY = 60


def grown(layer: Mapping[str, Any], params: Mapping[str, Any], invade: float) -> float:
    """Глубина проникновения: растёт как корень из времени и тем больше, чем выше проницаемость (условный закон)."""
    return params["depth_max"] * math.sqrt(max(0.0, invade) * layer["perm"]) if layer["perm"] > 0 else 0.0


def extent(layer: Mapping[str, Any], params: Mapping[str, Any], invade: float, dissipate: float) -> float:
    """Остаток зоны: время полного расформирования тем больше, чем больше зона и меньше проницаемость."""
    start = grown(layer, params, invade)
    if start <= 0 or dissipate <= 0:
        return start
    need = 0.55 * (start / params["depth_max"]) / layer["perm"]
    return start * max(0.0, 1 - dissipate / max(need, 1e-6))


def reading(layer: Mapping[str, Any], probe: Mapping[str, Any], zone: float) -> float:
    """Показание — взвешенное среднее по радиусу, вес убывает с расстоянием; доля зоны берётся из интеграла веса."""
    share = (1 - math.exp(-zone / probe["depth"])) / (1 - math.exp(-1 / probe["depth"]))
    return layer["native"] + (layer["invaded"] - layer["native"]) * min(1.0, share)


def check(params: Mapping[str, Any], beats: Sequence[Mapping[str, Any]]) -> list[str]:
    layers, probes = params.get("layers") or [], params.get("probes") or []
    if params.get("mode") not in ("resistivity", "neutron") or not 2 <= len(layers) <= 4 or not 1 <= len(probes) <= 2:
        return ["нужны mode, 2–4 слоя и 1–2 зонда"]
    need = ("label", "lith", "perm", "native", "invaded")
    if any(k not in x for x in layers for k in need) or any(k not in p for p in probes for k in ("label", "depth", "curve")) or not 0.2 <= params.get("depth_max", 0) <= 0.8:
        return ["у слоя нужны label, lith, perm, native, invaded; у зонда label, depth, curve; depth_max от 0.2 до 0.8"]
    issues = [f"{x['label']}: perm от 0 до 1, native и invaded больше нуля" for x in layers if not 0 <= x["perm"] <= 1 or min(x["native"], x["invaded"]) <= 0]
    issues += [f"{x['label']}: непроницаемая порода без проникновения и флюида" for x in layers if x["lith"] in ("shale", "dense") and (x["perm"] > 0 or x.get("fluid"))]
    issues += [f"{x['label']}: неизвестная порода" for x in layers if x["lith"] not in ("sand", "limestone", "dense", "shale")]
    fluids = [x["fluid"] for x in layers if x.get("fluid")]
    if any(f not in ORDER for f in fluids) or any(ORDER.index(a) > ORDER.index(b) for a, b in zip(fluids, fluids[1:], strict=False)):
        issues.append("газ над нефтью, нефть над водой")
    if params["mode"] == "neutron":
        gas = [x["native"] for x in layers if x.get("fluid") == "gas"]
        rest = [x["native"] for x in layers if x.get("fluid") in ("oil", "water")]
        if gas and rest and min(gas) <= max(rest):
            issues.append("neutron: против газа показание больше, чем против нефти и воды")
    if any(p["curve"] not in ("RES", "RES_SHALLOW", "NEUTRON") or not 0.05 <= p["depth"] <= 1 for p in probes):
        issues.append("зонд: curve RES, RES_SHALLOW или NEUTRON; depth от 0.05 до 1")
    if not 0 <= params.get("contact", 0) < len(layers):
        issues.append("contact: номер слоя, под которым контакт, или 0")
    issues += [f"действия {k} у шаблона нет" for b in beats for k in b["action"] if k not in ACTIONS]
    for key in ("invade", "dissipate", "casing"):
        values = [b["action"][key] for b in beats if key in b["action"]]
        if any(b < a for a, b in zip(values, values[1:], strict=False)) or any(not 0 <= v <= 1 for v in values):
            issues.append(f"{key} только растёт, от 0 до 1")
    cased = leaving = 0.0
    entered = 0.0
    for b in beats:
        cased = b["action"].get("casing", cased)
        if b["action"].get("invade", entered) > entered and (cased > 0 or leaving > 0):
            issues.append("invade: после спуска колонны или начала расформирования зона не растёт")
        entered = b["action"].get("invade", entered)
        leaving = b["action"].get("dissipate", leaving)
    return issues


def initial(params: Mapping[str, Any]) -> dict[str, float]:
    return {"invade": 0.0, "dissipate": 0.0, "casing": 0.0, "tracks": 0.0, "history": 0.0, "contact": 0.0, "focus": 0.0, "true_scale": 0.0}


def plaque(params: Mapping[str, Any], kind: str) -> str:
    return "скважина и слои не в масштабе"


def _boxes(area: tuple[float, float, float, float], layout: Any) -> list[tuple[float, float, float, float]]:
    x, y, w, h = area
    gap = layout.small * 0.5
    if layout.height > layout.width:
        low = h * 0.34
        return [(x, y, w * 0.6, h - low - gap), (x + w * 0.6 + gap, y, w * 0.4 - gap, h - low - gap), (x, y + h - low, w, low)]
    return [(x, y, w * 0.44, h), (x + w * 0.44 + gap, y, w * 0.2, h), (x + w * 0.64 + 2 * gap, y, w * 0.36 - 2 * gap, h)]


def _edges(params: Mapping[str, Any], box: tuple[float, float, float, float], layout: Any) -> list[float]:
    _, y, _, h = box
    top = y + layout.small * 2.2
    step = (h - layout.small * 2.6) / len(params["layers"])
    return [top + i * step for i in range(len(params["layers"]) + 1)]


def draw(ctx: cairo.Context, area: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float,
         style: Mapping[str, Any], layout: Any) -> None:
    boxes = _boxes(area, layout)
    for (x, y, w, h), painter, alpha in zip(boxes, (_section, _tracks, _history), (1.0, state["tracks"], state["history"]), strict=True):
        if alpha < 0.02:
            continue
        fill_rect(ctx, x, y, w, h, style["panel"], alpha, 14)
        ctx.save()
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        painter(ctx, (x, y, w, h), params, state, t, alpha, style, layout)
        ctx.restore()


def _section(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float, alpha: float,
             style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, h = box
    edges = _edges(params, box, layout)
    bore, view = w * 0.16, w * 0.8
    for number, (layer, y1, y2) in enumerate(zip(params["layers"], edges[:-1], edges[1:], strict=True), start=1):
        fill_rect(ctx, x, y1, w, y2 - y1, style["lithology"][layer["lith"]]["color"])
        zone = extent(layer, params, state["invade"], state["dissipate"]) * view
        rng = random.Random(number)
        if layer.get("fluid"):
            for _ in range(int(view * (y2 - y1) / 520)):
                px, py = x + bore + rng.random() * view, y1 + 8 + rng.random() * (y2 - y1 - 16)
                # у самого края зоны фильтрат и флюид пласта перемешаны
                near = px - x - bore < zone * (0.92 + 0.16 * rng.random())
                dot(ctx, px, py, 7, "#0F1419", 0.5)
                dot(ctx, px, py, 5.6, style["fluids"]["filtrate" if near else layer["fluid"]]["color"])
        else:
            for _ in range(int(view * (y2 - y1) / 1600)):
                px, py = x + bore + rng.random() * view, y1 + rng.random() * (y2 - y1)
                polyline(ctx, [(px, py), (px + 16, py)], "#0F1419", 2, 0.3)
        if zone > 6:
            polyline(ctx, [(x + bore + zone, y1 + 4), (x + bore + zone, y2 - 4)], style["text"], 4, 0.8, (10, 8))
            moving = 1 if state["dissipate"] <= 0 else -1
            if state["casing"] < 0.5 or moving < 0:
                for share in (0.35, 0.65):
                    cy = y1 + (y2 - y1) * share
                    start = x + bore + max(20.0, zone - 60) if moving > 0 else x + bore + zone + 60
                    arrow(ctx, start, cy, start + moving * 50, cy, style["fluids"]["filtrate" if moving > 0 else layer["fluid"]]["color"], 6)
        polyline(ctx, [(x, y2), (x + w, y2)], "#0F1419", 2, 0.5)
        text(ctx, x + w - 12, y1 + layout.small * 0.95, layer["label"], layout.small * 0.82, "#0F1419", True, "end")
        if round(state["focus"]) == number and state["focus"] > 0.5:
            ctx.set_source_rgba(1, 1, 1, 0.9)
            ctx.set_line_width(6)
            ctx.rectangle(x + 4, y1 + 3, w - 8, y2 - y1 - 6)
            ctx.stroke()
    fill_rect(ctx, x, edges[0], bore, edges[-1] - edges[0], style["fluids"]["mud"]["color"])
    rng = random.Random(9)
    for _ in range(40):
        place = (rng.random() - t * 0.05) % 1
        dot(ctx, x + bore * (0.15 + 0.7 * rng.random()), edges[0] + place * (edges[-1] - edges[0]), 3, "#ECEFF4", 0.35 * (1 - state["casing"]))
    if state["casing"] > 0.01:
        fill_rect(ctx, x + bore - 12, edges[0], 12, (edges[-1] - edges[0]) * state["casing"], "#B8C2CC")
        text(ctx, x + bore + 8, edges[-1] - 12, "колонна", layout.small * 0.72, "#0F1419", True, "start", state["casing"])
    arrow(ctx, x + 14, y + 10, x + 14, y + layout.small * 1.8, style["muted"], 4)
    text(ctx, x + 30, y + layout.small * 1.4, "глубина", layout.small * 0.75, style["muted"])
    text(ctx, x + w - 12, y + layout.small * 1.4, "от скважины →", layout.small * 0.75, style["muted"], False, "end")
    if state["contact"] > 0.01 and params.get("contact"):
        line = edges[params["contact"]]
        polyline(ctx, [(x, line), (x + w, line)], style["measurement"]["color"], 6, state["contact"], (16, 10))


def _range(params: Mapping[str, Any]) -> tuple[float, float]:
    values = [v for x in params["layers"] for v in (x["native"], x["invaded"])]
    pad = (max(values) - min(values)) * 0.15 or 1.0
    return min(values) - pad, max(values) + pad


def _tracks(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float, alpha: float,
            style: Mapping[str, Any], layout: Any) -> None:
    x, y, w, _ = box
    edges, (low, high) = _edges(params, box, layout), _range(params)
    for number, probe in enumerate(params["probes"]):
        color = style["curves"][probe["curve"]]["color"]
        points: list[tuple[float, float]] = []
        for layer, y1, y2 in zip(params["layers"], edges[:-1], edges[1:], strict=True):
            value = reading(layer, probe, extent(layer, params, state["invade"], state["dissipate"]))
            px = x + 14 + (value - low) / (high - low) * (w - 28)
            points += [(px, y1 + (y2 - y1) * 0.06), (px, y2 - (y2 - y1) * 0.06)]
        polyline(ctx, points, color, 7, alpha, () if number == 0 else (16, 9))
        text(ctx, x + 12 + number * w * 0.48, y + layout.small * 0.95, probe["label"], layout.small * 0.8, color, True, "start", alpha)
    text(ctx, x + w - 10, y + layout.small * 1.9, "больше →", layout.small * 0.62, style["muted"], False, "end", alpha)
    for edge in edges:
        polyline(ctx, [(x, edge), (x + w, edge)], style["muted"], 1.5, 0.35 * alpha)
    if state["contact"] > 0.01 and params.get("contact"):
        polyline(ctx, [(x, edges[params["contact"]]), (x + w, edges[params["contact"]])], style["measurement"]["color"], 6, state["contact"], (16, 10))


def _history(ctx: cairo.Context, box: tuple[float, float, float, float], params: Mapping[str, Any], state: Mapping[str, float], t: float, alpha: float,
             style: Mapping[str, Any], layout: Any) -> None:
    """Первая половина оси — рост зоны, вторая — расформирование; точка стоит на нынешнем состоянии."""
    x, y, w, h = box
    (low, high), probe = _range(params), params["probes"][-1]
    left, right, top, bottom = x + w * 0.05, x + w * 0.96, y + h * 0.16, y + h * 0.72
    text(ctx, left, y + layout.small * 1.0, f"{probe['label']} во времени", layout.small * 0.8, style["muted"], True, "start", alpha)
    polyline(ctx, [(left, top), (left, bottom), (right, bottom)], style["muted"], 3, alpha)
    text(ctx, right, bottom + layout.small * 0.85, "время →", layout.small * 0.7, style["muted"], False, "end", alpha)
    now = 0.4 * state["invade"] + 0.6 * state["dissipate"]
    colors = [style["fluids"][layer["fluid"]]["color"] if layer.get("fluid") else style["muted"] for layer in params["layers"]]
    for number, (layer, color) in enumerate(zip(params["layers"], colors, strict=True)):
        points = []
        for i in range(HISTORY + 1):
            moment = now * i / HISTORY
            zone = extent(layer, params, min(state["invade"], moment / 0.4), max(0.0, (moment - 0.4 * state["invade"]) / 0.6))
            points.append((left + (right - left) * moment, bottom - (reading(layer, probe, zone) - low) / (high - low) * (bottom - top)))
        polyline(ctx, points, color, 6, alpha, () if number % 2 == 0 else (14, 8))
        dot(ctx, *points[-1], 10, color, alpha)
        row = bottom + layout.small * (0.95 + 0.85 * (number // 2))
        column = left + (number % 2) * w * 0.36
        polyline(ctx, [(column, row - 10), (column + 34, row - 10)], color, 6, alpha, () if number % 2 == 0 else (10, 6))
        text(ctx, column + 44, row, layer["label"], layout.small * 0.7, style["text"], False, "start", alpha)


def stable(params: Mapping[str, Any], state: Mapping[str, float]) -> list[bool]:
    """В каких слоях зона уже расформирована."""
    return [extent(x, params, state["invade"], state["dissipate"]) <= 1e-9 for x in params["layers"]]

