"""Окно давлений по глубине: поровое — раствор — гидроразрыв; все линии считаются из одной модели слоёв."""

from collections.abc import Mapping, Sequence
from typing import Any

from glava.sdk.drawing import FONT, LINE, PAD, W, arrow, legend, line, lines, path, text, wrap

LABEL = "симуляция"
FRAME_CLASS = "A"
OUTCOMES = {"window": "раствор в окне", "kick": "риск проявления", "loss": "риск поглощения", "both": "риск проявления и поглощения"}
SUMMARY = """mudwindow — совмещённый график давлений по глубине: поровое давление, раствор, гидроразрыв (начало поглощения), башмаки колонн; показывает, почему нужна следующая колонна, где риск проявления или поглощения. data: {"axis":"density|pressure","layers":[сверху вниз {"label":"до 18 знаков","thickness":1|2,"pore":1..9,"frac":1..9}],"intervals":[сверху вниз {"to":номер последнего слоя интервала,"mud":1..9,"ecd":1..9 или null,"outcome":"window|kick|loss|both"}]}. 2–6 слоёв, 1–4 интервала бурения, последний доходит до нижнего слоя; в интервале один раствор. axis: density — эквивалентная плотность (градиент), pressure — давление, код умножает на глубину. pore, frac, mud, ecd — условные уровни эквивалентной плотности, на рисунке без чисел; frac выше pore; ecd — при циркуляции, не ниже mud. outcome обязан следовать из уровней: kick — раствор в покое ниже порового, loss — раствор (или ecd) выше гидроразрыва. Соотношения уровней — только названные в утверждениях или прямо из них следующие."""
LEVEL = {"type": "number", "minimum": 1, "maximum": 9}
SCHEMA = {
    "type": "object", "required": ["axis", "layers", "intervals"], "additionalProperties": False,
    "properties": {
        "axis": {"enum": ["density", "pressure"]},
        "layers": {"type": "array", "minItems": 2, "maxItems": 6, "items": {
            "type": "object", "required": ["label", "thickness", "pore", "frac"], "additionalProperties": False,
            "properties": {"label": {"type": "string", "minLength": 1, "maxLength": 20}, "thickness": {"enum": [1, 2]}, "pore": LEVEL, "frac": LEVEL}}},
        "intervals": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
            "type": "object", "required": ["to", "mud", "outcome"], "additionalProperties": False,
            "properties": {"to": {"type": "integer", "minimum": 1, "maximum": 6}, "mud": LEVEL,
                           "ecd": {"type": ["number", "null"], "minimum": 1, "maximum": 9}, "outcome": {"enum": list(OUTCOMES)}}}},
    },
}
UNIT_H = 64
LABEL_W = 150
LEFT, RIGHT = PAD + LABEL_W + 10, W - PAD - 6
Points = list[tuple[float, float]]


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    layers, intervals = data["layers"], data["intervals"]
    issues = [f"слой «{x['label']}»: гидроразрыв должен быть выше порового давления" for x in layers if x["frac"] <= x["pore"]]
    issues += [f"подпись «{x['label']}» не влезает в слой: короче или толще слой" for x in layers
               if len(wrap(x["label"], LABEL_W - 12)) * LINE > x["thickness"] * UNIT_H]
    ends = [i["to"] for i in intervals]
    if ends != sorted(set(ends)) or ends[-1] != len(layers):
        return [*issues, "to растёт от интервала к интервалу, последний — номер нижнего слоя"]
    for number, (part, interval) in enumerate(zip(_parts(layers, intervals), intervals, strict=True), start=1):
        if (interval.get("ecd") or interval["mud"]) < interval["mud"]:
            issues.append(f"интервал {number}: при циркуляции давление на забой не ниже, чем в покое")
        real = outcome_of(part, interval)
        if real != interval["outcome"]:
            issues.append(f"интервал {number}: из уровней следует outcome {real}, а не {interval['outcome']}")
    return issues


def _parts(layers: Sequence[Mapping], intervals: Sequence[Mapping]) -> list[Sequence[Mapping]]:
    starts = [0, *(i["to"] for i in intervals)]
    return [layers[a:b] for a, b in zip(starts, starts[1:], strict=False)]


def outcome_of(layers: Sequence[Mapping], interval: Mapping[str, Any]) -> str:
    """Что следует из уровней: сравнение во всех открытых слоях, а не только на забое."""
    top = interval.get("ecd") or interval["mud"]
    kick = any(interval["mud"] < x["pore"] for x in layers)
    loss = any(top > x["frac"] for x in layers)
    return "both" if kick and loss else "kick" if kick else "loss" if loss else "window"


def _tops(layers: Sequence[Mapping], start: float) -> list[float]:
    tops = [start]
    for layer in layers:
        tops = [*tops, tops[-1] + layer["thickness"] * UNIT_H]
    return tops


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    layers, intervals = data["layers"], data["intervals"]
    top = PAD + LINE + 14.0
    tops = _tops(layers, top)
    parts = _parts(layers, intervals)
    bounds = [(0 if i == 0 else intervals[i - 1]["to"], x["to"]) for i, x in enumerate(intervals)]
    peak = max([x["frac"] for x in layers] + [i.get("ecd") or i["mud"] for i in intervals]) + 0.6
    pressure = data["axis"] == "pressure"

    def at(level: float, y: float) -> tuple[float, float]:
        share = level / peak * ((y - top) / (tops[-1] - top) if pressure else 1)
        return LEFT + share * (RIGHT - LEFT), y

    def steps(levels: Sequence[float], first: int = 0) -> Points:
        return [at(v, tops[first + k + e]) for k, v in enumerate(levels) for e in (0, 1)]

    pore, frac = steps([x["pore"] for x in layers]), steps([x["frac"] for x in layers])
    curves = style["curves"]
    body = text(PAD, PAD + FONT, "глубина", style["muted"]) + arrow(PAD + 100, PAD + 4, PAD + 100, PAD + FONT + 6, style["muted"], 2, 6)
    body += "".join(path([pore[k], frac[k], frac[k + 1], pore[k + 1]], "none", 0, fill=style["panel"], closed=True) for k in range(0, len(pore), 2))
    body += "".join(_risks(part, interval, start, tops, at, style) for part, interval, (start, _) in zip(parts, intervals, bounds, strict=True))
    for i, layer in enumerate(layers):
        rows = wrap(layer["label"], LABEL_W - 12)
        middle = (tops[i] + tops[i + 1]) / 2
        body += line(PAD, tops[i], RIGHT, tops[i], style["panel"], 2) + lines(PAD, middle + 8 - (len(rows) - 1) * LINE / 2, rows, style["text"])
    body += path(pore, curves["PORE"]["color"], 4) + path(frac, curves["FRAC"]["color"], 4)
    for interval, (start, end) in zip(intervals, bounds, strict=True):
        ends = (tops[start], tops[end])
        body += path([at(interval["mud"], y) for y in ends], curves["MUD"]["color"], 4)
        if interval.get("ecd"):
            body += path([at(interval["ecd"], y) for y in ends], curves["ECD"]["color"], 3, extra='stroke-dasharray="9 6"')
    body += "".join(_shoe(tops[end], style) for _, end in bounds[:-1])
    body += arrow(LEFT, top, LEFT, tops[-1] + 8, style["muted"], 2, 7) + arrow(LEFT, tops[-1], RIGHT + 6, tops[-1], style["muted"], 2, 7)
    foot = wrap(f"{'давление' if pressure else 'эквивалентная плотность'} →", W - 2 * PAD)
    body += lines(RIGHT, tops[-1] + FONT + 12, foot, style["muted"], "end")
    drawn, y = legend(_legend_items(data, style), tops[-1] + LINE * len(foot) + 20, style["text"])
    results = [f"{number}. {OUTCOMES[i['outcome']]}" for number, i in enumerate(intervals, start=1)] if len(intervals) > 1 else [OUTCOMES[intervals[0]["outcome"]]]
    note = [*(r for x in (["Интервалы сверху вниз:"] if len(intervals) > 1 else []) + results for r in wrap(x, W - 2 * PAD)),
            *wrap("Без чисел: показано только соотношение", W - 2 * PAD)]
    return body + drawn + lines(PAD, y + FONT, note, style["muted"]), y + LINE * len(note) + 8


def _risks(part: Sequence[Mapping], interval: Mapping[str, Any], start: int, tops: Sequence[float], at: Any, style: Mapping[str, Any]) -> str:
    """Закрашено там, где раствор вышел из окна: ниже порового или выше гидроразрыва."""
    out = ""
    upper = interval.get("ecd") or interval["mud"]
    for k, layer in enumerate(part, start=start):
        for wrong, low, high, key in ((interval["mud"] < layer["pore"], interval["mud"], layer["pore"], "kick"), (upper > layer["frac"], layer["frac"], upper, "loss")):
            if wrong:
                y1, y2 = tops[k], tops[k + 1]
                out += path([at(low, y1), at(high, y1), at(high, y2), at(low, y2)], "none", 0, fill=style["hazards"][key]["color"], closed=True, extra='fill-opacity="0.75"')
    return out


def _shoe(y: float, style: Mapping[str, Any]) -> str:
    """Граница интервала: выше неё ствол закрыт колонной."""
    steel = style["wellbore"]["steel"]["color"]
    mark = path([(LEFT, y - 16), (LEFT, y), (LEFT + 16, y)], style["text"], 1, fill=steel, closed=True)
    return line(LEFT, y, RIGHT, y, style["text"], 2, "4 6") + mark


def _legend_items(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[tuple[str, str]]:
    curves, hazards = style["curves"], style["hazards"]
    outcomes = {i["outcome"] for i in data["intervals"]}
    items = [(curves[k]["color"], curves[k]["ru"]) for k in ("PORE", "FRAC", "MUD")]
    items += [(style["panel"], "окно между поровым и гидроразрывом")]
    items += [(curves["ECD"]["color"], curves["ECD"]["ru"])] if any(i.get("ecd") for i in data["intervals"]) else []
    items += [(hazards["kick"]["color"], hazards["kick"]["ru"])] if outcomes & {"kick", "both"} else []
    items += [(hazards["loss"]["color"], hazards["loss"]["ru"])] if outcomes & {"loss", "both"} else []
    return items + ([(style["wellbore"]["steel"]["color"], "башмак: выше ствол закрыт колонной")] if len(data["intervals"]) > 1 else [])
