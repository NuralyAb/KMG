"""Планшет ГИС: кривые вычисляются из одной модели слоёв; проверки — физика отклика по чек-листу."""

from collections.abc import Mapping, Sequence
from typing import Any

from glava.scenes.canvas import FONT, LINE, PAD, W, arrow, legend, line, lines, path, rect, text, wrap

LABEL = "симуляция"
FRAME_CLASS = "A"
FLUIDS = ("gas", "oil", "water")
LEVELS = {"low": 0.16, "mid": 0.5, "high": 0.84}
CURVES = ("SP", "GR", "RES", "RES_SHALLOW", "NEUTRON", "DENSITY", "SONIC", "CALIPER")
SUMMARY = """log — планшет ГИС, отклик кривых на слои; главный шаблон для признаков на диаграммах. data: {"layers":[сверху вниз {"lithology":"sand|shale|limestone|dolomite|anhydrite|salt|dense|reef","fluid":"gas|oil|water"(только у коллектора),"label":"до 16 знаков","thickness":1|2|3}],"curves":[{"name":"SP|GR|RES|RES_SHALLOW|NEUTRON|DENSITY|SONIC|CALIPER","levels":[по одному на слой "low|mid|high"]}],"filtrate":"fresh|salt"}. 2–6 слоёв, 1–3 кривые. SP: low — отрицательная аномалия; CALIPER: low — диаметр меньше номинального, mid — номинальный, high — больше; NEUTRON — показания НГК; SONIC — интервальное время; DENSITY — плотность. Показывай только то, что сказано в утверждениях узла."""
SCHEMA = {
    "type": "object", "required": ["layers", "curves"], "additionalProperties": False,
    "properties": {
        "layers": {"type": "array", "minItems": 2, "maxItems": 6, "items": {
            "type": "object", "required": ["lithology", "label", "thickness"], "additionalProperties": False,
            "properties": {"lithology": {"enum": ["sand", "shale", "limestone", "dolomite", "anhydrite", "salt", "dense", "reef"]},
                           "fluid": {"enum": [*FLUIDS, None]}, "label": {"type": "string", "maxLength": 20}, "thickness": {"enum": [1, 2, 3]}}}},
        "curves": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
            "type": "object", "required": ["name", "levels"], "additionalProperties": False,
            "properties": {"name": {"enum": list(CURVES)}, "levels": {"type": "array", "items": {"enum": list(LEVELS)}}}}},
        "filtrate": {"enum": ["fresh", "salt"]},
    },
}
NAMES = {"SP": "ПС", "GR": "ГК", "RES": "КС", "RES_SHALLOW": "МКЗ", "NEUTRON": "НГК", "DENSITY": "ГГК-П", "SONIC": "АК", "CALIPER": "КВ"}
FULL = {"SP": "потенциал собственной поляризации", "GR": "гамма-каротаж", "RES": "кажущееся сопротивление", "RES_SHALLOW": "микрозонд", "NEUTRON": "нейтронный каротаж",
        "DENSITY": "плотностной каротаж", "SONIC": "акустический каротаж", "CALIPER": "диаметр скважины"}
RESERVOIRS = {"sand", "limestone", "dolomite", "reef"}
TIGHT = {"dense", "anhydrite", "salt"}
UNIT_H = 46
LITHO_W = 168
BLUR = 7


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    layers = data["layers"]
    issues = [f"{c['name']}: уровней {len(c['levels'])}, слоёв {len(layers)}" for c in data["curves"] if len(c["levels"]) != len(layers)]
    issues += [f"слой «{x['label']}»: флюид только в коллекторе" for x in layers if x.get("fluid") and x["lithology"] not in RESERVOIRS]
    for x in layers:
        if len(wrap(x["label"], LITHO_W - 34)) * LINE > x["thickness"] * UNIT_H:
            issues.append(f"подпись «{x['label']}» не влезает в слой: короче или толще слой")
    if issues:
        return issues
    if len({c["name"] for c in data["curves"]}) != len(data["curves"]):
        issues.append("кривая повторяется")
    for upper, lower in zip(layers, layers[1:], strict=False):
        a, b = upper.get("fluid"), lower.get("fluid")
        if a and b and upper["lithology"] == lower["lithology"] and FLUIDS.index(a) > FLUIDS.index(b):
            issues.append(f"в одном пласте {b} под {a}: газ над нефтью, нефть над водой")
    for curve in data["curves"]:
        rule = RULES.get(curve["name"])
        if rule:
            issues += rule(Response([LEVELS[v] for v in curve["levels"]], layers, data.get("filtrate", "fresh")))
    return issues


class Response:
    """Отклик одной кривой, разложенный по типам слоёв."""

    def __init__(self, values: Sequence[float], layers: Sequence[Mapping], filtrate: str) -> None:
        pairs = list(zip(values, layers, strict=True))
        self.filtrate = filtrate
        self.shale = [v for v, x in pairs if x["lithology"] == "shale"]
        self.clean = [v for v, x in pairs if x["lithology"] != "shale"]
        self.tight = [v for v, x in pairs if x["lithology"] in TIGHT]
        self.heavy = [v for v, x in pairs if x["lithology"] in {"dense", "anhydrite"}]
        self.porous = [v for v, x in pairs if x["lithology"] in RESERVOIRS]
        self.liquid = [v for v, x in pairs if x["lithology"] in RESERVOIRS and x.get("fluid") in ("oil", "water")]
        self.pay = [v for v, x in pairs if x.get("fluid") in ("oil", "gas")]
        self.water = [v for v, x in pairs if x.get("fluid") == "water"]


def _above(higher: Sequence[float], lower: Sequence[float], strict: bool = True) -> bool:
    if not higher or not lower:
        return True
    return min(higher) > max(lower) if strict else min(higher) >= max(lower)


def _gamma(r: Response) -> list[str]:
    return [] if _above(r.shale, r.clean) else ["ГК: у глины показания выше, чем у остальных слоёв"]


def _sp(r: Response) -> list[str]:
    good = _above(r.shale, r.porous, False) if r.filtrate == "fresh" else _above(r.porous, r.shale, False)
    return [] if good else ["ПС: знак аномалии против коллектора не соответствует минерализации фильтрата"]


def _resistivity(r: Response) -> list[str]:
    issues = [] if _above(r.pay, r.water) else ["КС: нефтегазонасыщенный слой имеет сопротивление выше водонасыщенного"]
    issues += [] if _above(r.pay, r.shale) else ["КС: глина не выше нефтегазонасыщенного слоя"]
    return issues + _shallow(r)


def _shallow(r: Response) -> list[str]:
    return [] if _above(r.tight, r.shale) else ["сопротивление плотной породы, ангидрита и соли выше, чем у глины"]


def _neutron(r: Response) -> list[str]:
    issues = [] if _above(r.clean, r.shale) else ["НГК: у глины показания самые низкие"]
    return issues + ([] if _above(r.heavy, r.liquid, False) else ["НГК: у плотной породы показания не ниже, чем у коллектора с жидкостью"])


def _density(r: Response) -> list[str]:
    return [] if _above(r.heavy, r.porous, False) else ["ГГК-П: плотная порода не легче коллектора"]


def _sonic(r: Response) -> list[str]:
    return [] if _above(r.shale, r.tight) else ["АК: интервальное время в плотной породе меньше, чем в глине"]


def _caliper(r: Response) -> list[str]:
    nominal = LEVELS["mid"]
    issues = ["кавернограмма: против глины диаметр не уменьшается"] if any(v < nominal for v in r.shale) else []
    issues += ["кавернограмма: против проницаемого коллектора диаметр не увеличивается"] if any(v > nominal for v in r.porous) else []
    return issues + (["кавернограмма: глинистая корка бывает только против коллектора"] if any(v < nominal for v in r.tight) else [])


RULES = {"GR": _gamma, "SP": _sp, "RES": _resistivity, "RES_SHALLOW": _shallow, "NEUTRON": _neutron, "DENSITY": _density, "SONIC": _sonic,
         "CALIPER": _caliper}


def _smooth(levels: Sequence[float], layers: Sequence[Mapping]) -> list[float]:
    """Сигнал прибора: ступени модели, сглаженные окном измерения."""
    steps = [v for v, x in zip(levels, layers, strict=True) for _ in range(x["thickness"] * 20)]
    windows = [steps[max(0, i - BLUR): i + BLUR + 1] for i in range(len(steps))]
    return [sum(w) / len(w) for w in windows]


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    layers, curves = data["layers"], data["curves"]
    top = PAD + LINE + 14
    height = sum(x["thickness"] for x in layers) * UNIT_H
    track_x = PAD + LITHO_W + 8
    track_w = (W - PAD - track_x) / len(curves)
    body = text(PAD + 26, PAD + FONT, "глубина", style["muted"]) + arrow(PAD + 10, PAD + 4, PAD + 10, PAD + FONT + 6, style["muted"], 2, 6)
    y = float(top)
    for layer in layers:
        h = layer["thickness"] * UNIT_H
        body += rect(PAD, y, LITHO_W, h, style["lithology"][layer["lithology"]]["color"], stroke=style["background"])
        if layer.get("fluid"):
            body += rect(PAD, y, 16, h, style["fluids"][layer["fluid"]]["color"])
        rows = wrap(layer["label"], LITHO_W - 34)[: max(1, int(h // LINE))]
        body += lines(PAD + 26, y + h / 2 + 8 - (len(rows) - 1) * LINE / 2, rows, "#0F1419", weight=600)
        body += line(track_x, y, W - PAD, y, style["panel"], 2)
        y += h
    for i, curve in enumerate(curves):
        x0 = track_x + i * track_w
        color = style["curves"][curve["name"]]["color"]
        body += rect(x0, top, track_w - 6, height, "none", stroke=style["panel"], extra='stroke-width="2"')
        body += text(x0 + track_w / 2 - 3, PAD + FONT, NAMES[curve["name"]], color, "middle", 600)
        if curve["name"] == "CALIPER":
            body += line(x0 + (track_w - 6) / 2, top, x0 + (track_w - 6) / 2, top + height, style["muted"], 2, "6 6")
        samples = _smooth([LEVELS[v] for v in curve["levels"]], layers)
        body += path([(x0 + v * (track_w - 6), top + k / (len(samples) - 1) * height) for k, v in enumerate(samples)], color, 4)
    used = list(dict.fromkeys(x["fluid"] for x in layers if x.get("fluid")))
    items = [(style["curves"][c["name"]]["color"], f"{NAMES[c['name']]}: {FULL[c['name']]}, рост вправо") for c in curves]
    drawn, y = legend(items + [(style["fluids"][f]["color"], style["fluids"][f]["ru"]) for f in used], top + height + 10, style["text"])
    note: list[str] = []
    if any(c["name"] == "SP" for c in curves):
        fresh = data.get("filtrate", "fresh") == "fresh"
        note = wrap(f"ПС показана, когда фильтрат {'преснее' if fresh else 'солёнее'} пластовой воды", W - 2 * PAD)
    note = [*note, *wrap("Русская школа обозначений. Без масштаба", W - 2 * PAD)]
    return body + drawn + lines(PAD, y + FONT, note, style["muted"]), y + LINE * len(note) + 8
