"""Геологический разрез: слои и контакты из одной модели, флюиды разделены по плотности."""

import math
from collections.abc import Mapping, Sequence
from typing import Any

from glava.sdk.drawing import FONT, LINE, PAD, W, legend, line, lines, path, rect, text, wrap

LABEL = "схема"
FRAME_CLASS = "B"
FLUIDS = ("gas", "oil", "water")
SEALS = {"shale", "salt", "anhydrite", "dense"}
SUMMARY = """section — геологический разрез: залегание слоёв, ловушка, контакты, скважины. data: {"shape":"flat|anticline|pinchout|fault|reef","layers":[сверху вниз {"lithology":"sand|shale|limestone|dolomite|anhydrite|salt|dense|reef","label":"до 18 знаков","fluids":["gas","oil","water"] по порядку сверху вниз, только у коллектора}],"wells":[{"x":0.1..0.9,"label":"до 6 знаков"}]}. 2–5 слоёв. Над слоем с газом или нефтью — покрышка (shale, salt, anhydrite, dense). pinchout: второй слой выклинивается вправо; fault: правая часть опущена; reef: второй слой — рифовый массив."""
SCHEMA = {
    "type": "object", "required": ["shape", "layers"], "additionalProperties": False,
    "properties": {
        "shape": {"enum": ["flat", "anticline", "pinchout", "fault", "reef"]},
        "layers": {"type": "array", "minItems": 2, "maxItems": 5, "items": {
            "type": "object", "required": ["lithology", "label"], "additionalProperties": False,
            "properties": {"lithology": {"enum": ["sand", "shale", "limestone", "dolomite", "anhydrite", "salt", "dense", "reef"]},
                           "label": {"type": "string", "maxLength": 24}, "fluids": {"type": "array", "items": {"enum": list(FLUIDS)}}}}},
        "wells": {"type": "array", "maxItems": 4, "items": {
            "type": "object", "required": ["x", "label"], "additionalProperties": False,
            "properties": {"x": {"type": "number", "minimum": 0.05, "maximum": 0.95}, "label": {"type": "string", "maxLength": 8}}}},
    },
}
HEIGHT = 320
REAL_WIDTH_M, REAL_HEIGHT_M = 4000, 500
RISE = 60
FAULT_X, FAULT_DROP = 0.55, 50
STEPS = 80
WIDTH = W - 2 * PAD


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    layers = data["layers"]
    if data["shape"] in ("pinchout", "reef") and len(layers) < 3:
        issues.append("для выклинивания и рифа нужно не меньше трёх слоёв")
    if data["shape"] == "pinchout" and len(layers) > 1 and layers[1]["lithology"] in SEALS:
        issues.append("выклинивается второй слой, это должен быть коллектор")
    if data["shape"] == "reef" and len(layers) > 1 and layers[1]["lithology"] != "reef":
        issues.append("второй слой рифовой формы должен быть reef")
    for i, layer in enumerate(layers):
        fluids = layer.get("fluids") or []
        if not fluids:
            continue
        if layer["lithology"] in SEALS:
            issues.append(f"слой «{layer['label']}» — покрышка, флюидов в нём не показывают")
        if fluids != sorted(set(fluids), key=FLUIDS.index):
            issues.append("газ над нефтью, нефть над водой")
        if set(fluids) & {"gas", "oil"} and (i == 0 or layers[i - 1]["lithology"] not in SEALS):
            issues.append(f"над залежью «{layer['label']}» нужна покрышка")
        if set(fluids) & {"gas", "oil"} and "water" in fluids and data["shape"] == "flat":
            issues.append("в горизонтальном слое без ловушки залежь с водой не показывают: выберите форму ловушки")
    return issues


def _relief(shape: str, u: float, depth: float) -> float:
    if shape in ("anticline", "reef"):
        return -RISE * math.exp(-((u - 0.5) / 0.2) ** 2) * (1 if shape == "anticline" else 0.35 * (1 - depth))
    if shape == "fault":
        # пласт поднимается к разлому; правый блок опущен
        return FAULT_DROP if u > FAULT_X else -RISE * 0.8 * u / FAULT_X
    if shape == "pinchout":
        return -70 * (u - 0.5)
    return 0


def _thicknesses(data: Mapping[str, Any], u: float) -> list[float]:
    count = len(data["layers"])
    usable = HEIGHT - RISE - 20
    values = [usable / count] * count
    if data["shape"] == "pinchout":
        values[1] = max(0.0, usable / count * min(1.0, (0.72 - u) / 0.5))
        values[2] += usable / count - values[1]
    if data["shape"] == "reef":
        body = usable / count * (0.25 + 0.75 * math.exp(-((u - 0.5) / 0.22) ** 4))
        values[1], values[0] = body, values[0] + usable / count - body
    return values


def tops(data: Mapping[str, Any], u: float) -> list[float]:
    """Глубины кровель всех слоёв и подошвы последнего в точке u (0..1)."""
    y = [float(RISE)]
    for value in _thicknesses(data, u):
        y = [*y, y[-1] + value]
    return [0.0 if i == 0 else v + _relief(data["shape"], u, i / len(y)) for i, v in enumerate(y[:-1])] + [float(HEIGHT)]


def _polygon(data: Mapping[str, Any], index: int, top: float) -> list[tuple[float, float]]:
    grid = [i / STEPS for i in range(STEPS + 1)]
    grid = sorted({*grid, FAULT_X, FAULT_X + 1e-6}) if data["shape"] == "fault" else grid
    upper = [(PAD + u * WIDTH, top + tops(data, u)[index]) for u in grid]
    lower = [(PAD + u * WIDTH, top + tops(data, u)[index + 1]) for u in grid]
    return upper + lower[::-1]


def _fluid_bands(data: Mapping[str, Any], index: int) -> list[tuple[str, float, float]]:
    """Горизонтальные контакты: залежь занимает верх ловушки, вода — остальное."""
    fluids: Sequence[str] = data["layers"][index].get("fluids") or []
    roofs = [tops(data, i / STEPS)[index] for i in range(STEPS + 1)]
    floors = [tops(data, i / STEPS)[index + 1] for i in range(STEPS + 1)]
    crest = min(roofs)
    spill = min(max(roofs), crest + 46) if "water" in fluids and max(roofs) > crest else max(floors)
    hydrocarbons = [f for f in fluids if f != "water"]
    bands: list[tuple[str, float, float]] = []
    step = (spill - crest) / max(1, len(hydrocarbons))
    for k, fluid in enumerate(hydrocarbons):
        bands = [*bands, (fluid, crest + k * step, crest + (k + 1) * step)]
    return [*bands, ("water", spill if hydrocarbons else crest, float(HEIGHT))] if "water" in fluids else bands


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    layers, wells = data["layers"], data.get("wells") or []
    top = PAD + (LINE + 10 if wells else 0)
    body = f'<defs><clipPath id="frame"><rect x="{PAD}" y="{top}" width="{WIDTH}" height="{HEIGHT}"/></clipPath>'
    body += "".join(f'<clipPath id="layer{i}">{path(_polygon(data, i, top), "none", 0, closed=True)}</clipPath>' for i in range(len(layers))) + "</defs>"
    body += '<g clip-path="url(#frame)">'
    for i, layer in enumerate(layers):
        body += path(_polygon(data, i, top), style["background"], 2, fill=style["lithology"][layer["lithology"]]["color"], closed=True)
        for fluid, y1, y2 in _fluid_bands(data, i):
            body += rect(PAD, top + y1, WIDTH, y2 - y1, style["fluids"][fluid]["color"], extra=f'clip-path="url(#layer{i})" fill-opacity="0.78"')
    if data["shape"] == "fault":
        x = PAD + FAULT_X * WIDTH
        body += line(x, top, x, top + HEIGHT, style["background"], 5)
    body += "".join(line(PAD + w["x"] * WIDTH, top, PAD + w["x"] * WIDTH, top + tops(data, w["x"])[-2] + 20, "#0F1419", 5) for w in wells) + "</g>"
    for i in range(len(layers)):
        edge = tops(data, 0.04)
        body += text(PAD + 0.04 * WIDTH, top + (edge[i] + edge[i + 1]) / 2 + 8, str(i + 1), '#0F1419', 'middle', 600)
    for well in wells:
        body += text(PAD + well["x"] * WIDTH, PAD + FONT, well["label"], style["text"], "middle", 600)
    items = [(style["lithology"][x["lithology"]]["color"], f"{i}. {x['label']}") for i, x in enumerate(layers, start=1)]
    used = [f for f in FLUIDS if any(f in (x.get("fluids") or []) for x in layers)]
    items += [(style["fluids"][f]["color"], f"{style['fluids'][f]['ru']} в порах") for f in used]
    drawn, y = legend(items, top + HEIGHT + 12, style["text"])
    factor = (HEIGHT / REAL_HEIGHT_M) / (WIDTH / REAL_WIDTH_M)
    note = wrap(f"Глубина вниз. Вертикаль преувеличена примерно в {factor:.0f} раз", W - 2 * PAD)
    return body + drawn + lines(PAD, y + FONT, note, style["muted"]), y + LINE * len(note) + 8
