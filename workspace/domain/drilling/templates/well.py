"""Конструкция скважины: колонны, цемент, открытый ствол, перфорация; вложенность и башмаки проверяются до рисования."""

from collections.abc import Mapping, Sequence
from typing import Any

from glava.sdk.drawing import FONT, LINE, PAD, W, arrow, legend, line, lines, path, rect, text, wrap

LABEL = "схема"
FRAME_CLASS = "B"
KINDS = ("conductor", "surface", "intermediate", "production", "liner")
NAMES = {"conductor": "направление", "surface": "кондуктор", "intermediate": "промежуточная колонна",
         "production": "эксплуатационная колонна", "liner": "хвостовик"}
LITHOLOGY = ("sand", "shale", "limestone", "dolomite", "anhydrite", "salt", "dense", "reef")
RESERVOIRS = {"sand", "limestone", "dolomite", "reef"}
HAZARDS = ("loss", "kick", "unstable")
SUMMARY = """well — конструкция скважины: обсадные колонны, цемент за ними, башмаки, открытый ствол, перфорация, бурение под следующую колонну с путём раствора. data: {"layers":[сверху вниз {"lithology":"sand|shale|limestone|dolomite|anhydrite|salt|dense|reef","label":"до 18 знаков","thickness":1|2,"fluid":"gas|oil|water"(только у коллектора),"hazard":"loss|kick|unstable"(поглощение, проявление, неустойчивая стенка)}],"strings":[от внешней к внутренней {"kind":"conductor|surface|intermediate|production|liner","shoe":номер слоя с башмаком,"cement":"full|part|none"}],"bottom":номер слоя с забоем открытого ствола или null,"drilling":true|false,"perforated":номер слоя или null}. 2–6 слоёв, 1–5 колонн: направление, кондуктор, промежуточные, эксплуатационная, хвостовик. Башмак каждой следующей колонны в более глубоком слое. cement: full — до устья (у хвостовика до его головы), part — до низа предыдущей колонны, none — цемент не показан. drilling:true — в стволе бурильная колонна и стрелки прямой промывки, нужен bottom. perforated — слой коллектора, перекрытый только последней колонной. Осложнение и флюид — только названные в утверждениях; чего утверждения не называют (толщина, порода соседнего слоя), задавай нейтрально."""
SCHEMA = {
    "type": "object", "required": ["layers", "strings", "bottom", "drilling", "perforated"], "additionalProperties": False,
    "properties": {
        "layers": {"type": "array", "minItems": 2, "maxItems": 6, "items": {
            "type": "object", "required": ["lithology", "label", "thickness"], "additionalProperties": False,
            "properties": {"lithology": {"enum": list(LITHOLOGY)}, "label": {"type": "string", "minLength": 1, "maxLength": 20},
                           "thickness": {"enum": [1, 2]}, "fluid": {"enum": ["gas", "oil", "water", None]},
                           "hazard": {"enum": [*HAZARDS, None]}}}},
        "strings": {"type": "array", "minItems": 1, "maxItems": 5, "items": {
            "type": "object", "required": ["kind", "shoe", "cement"], "additionalProperties": False,
            "properties": {"kind": {"enum": list(KINDS)}, "shoe": {"type": "integer", "minimum": 1, "maximum": 6},
                           "cement": {"enum": ["full", "part", "none"]}}}},
        "bottom": {"type": ["integer", "null"], "minimum": 1, "maximum": 6},
        "drilling": {"type": "boolean"},
        "perforated": {"type": ["integer", "null"], "minimum": 1, "maximum": 6},
    },
}
UNIT_H = 64
LABEL_W = 156
AXIS = 296.0
OUTER, STEP, WALL = 78, 14, 5
RING = STEP - WALL
SHOE_AT, BOTTOM_AT = 0.7, 0.92
OVERLAP = 26
STRIP = 14


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    layers, strings = data["layers"], data["strings"]
    issues = [f"слой «{x['label']}»: флюид только в коллекторе" for x in layers if x.get("fluid") and x["lithology"] not in RESERVOIRS]
    issues += [f"подпись «{x['label']}» не влезает в слой: короче или толще слой" for x in layers
               if len(_label_rows(x["label"])) * LINE > x["thickness"] * UNIT_H]
    named = [s["shoe"] for s in strings] + [n for n in (data["bottom"], data["perforated"]) if n]
    if any(n > len(layers) for n in named):
        return [*issues, "номер слоя больше числа слоёв"]
    return issues + _string_issues(strings, layers) + _hole_issues(data)


def _string_issues(strings: Sequence[Mapping], layers: Sequence[Mapping]) -> list[str]:
    kinds = [s["kind"] for s in strings]
    issues = [] if kinds == sorted(kinds, key=KINDS.index) else ["порядок колонн: направление, кондуктор, промежуточная, эксплуатационная, хвостовик"]
    issues += [f"{NAMES[k]} бывает одна" for k in ("conductor", "surface", "production") if kinds.count(k) > 1]
    issues += ["хвостовику нужна предыдущая колонна"] if kinds[0] == "liner" else []
    issues += [f"башмак «{NAMES[b['kind']]}» должен быть глубже башмака «{NAMES[a['kind']]}»"
               for a, b in zip(strings, strings[1:], strict=False) if b["shoe"] <= a["shoe"]]
    return issues + [f"башмак «{NAMES[s['kind']]}» стоит в осложнённом слое: колонна должна его перекрыть"
                     for s in strings if s["kind"] not in ("production", "liner") and layers[s["shoe"] - 1].get("hazard")]


def _hole_issues(data: Mapping[str, Any]) -> list[str]:
    last, bottom, perforated = data["strings"][-1], data["bottom"], data["perforated"]
    issues = ["забой не может быть выше последнего башмака"] if bottom and bottom < last["shoe"] else []
    issues += ["для бурения укажите bottom: забой открытого ствола"] if data["drilling"] and not bottom else []
    if not perforated:
        return issues
    issues += [] if data["layers"][perforated - 1]["lithology"] in RESERVOIRS else ["перфорация показывается только в коллекторе"]
    issues += ["перфорация нужна только в обсаженном и готовом стволе"] if data["drilling"] or perforated > last["shoe"] else []
    issues += ["перфорируют эксплуатационную колонну или хвостовик"] if last["kind"] not in ("production", "liner") else []
    return issues + (["перфорированный слой закрыт ещё и предыдущей колонной"] if len(data["strings"]) > 1 and perforated <= data["strings"][-2]["shoe"] else [])


def _label_rows(label: str) -> list[str]:
    return wrap(label, LABEL_W - STRIP - 34)


def _tops(layers: Sequence[Mapping], start: float) -> list[float]:
    tops = [start]
    for layer in layers:
        tops = [*tops, tops[-1] + layer["thickness"] * UNIT_H]
    return tops


def _at(tops: Sequence[float], layer: int, share: float) -> float:
    return tops[layer - 1] + (tops[layer] - tops[layer - 1]) * share


def _band(half: float, inner: float, y1: float, y2: float, color: str) -> str:
    """Кольцо в разрезе: две полосы по сторонам оси."""
    return rect(AXIS - half, y1, half - inner, y2 - y1, color) + rect(AXIS + inner, y1, half - inner, y2 - y1, color)


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    layers, strings = data["layers"], data["strings"]
    surface = PAD + LINE + 14.0
    tops = _tops(layers, surface)
    body = text(PAD, PAD + FONT, "глубина", style["muted"]) + arrow(PAD + 100, PAD + 4, PAD + 100, PAD + FONT + 6, style["muted"], 2, 6)
    body += text(AXIS, PAD + FONT, "устье", style["muted"], "middle")
    body += "".join(_layer(layer, i, tops, style) for i, layer in enumerate(layers, start=1))
    body += _casing(data, tops, style) + _hole(data, tops, style)
    body += line(PAD, surface, W - PAD, surface, style["text"], 3)
    drawn, y = legend(_legend_items(data, style), tops[-1] + 12, style["text"])
    note = wrap("Глубина вниз. Ширина скважины сильно преувеличена, без масштаба", W - 2 * PAD)
    return body + drawn + lines(PAD, y + FONT, note, style["muted"]), y + LINE * len(note) + 8


def _layer(layer: Mapping[str, Any], number: int, tops: Sequence[float], style: Mapping[str, Any]) -> str:
    y, h = tops[number - 1], tops[number] - tops[number - 1]
    out = rect(PAD, y, W - 2 * PAD, h, style["lithology"][layer["lithology"]]["color"], stroke=style["background"])
    if layer.get("fluid"):
        out += rect(PAD, y, STRIP, h, style["fluids"][layer["fluid"]]["color"])
    if layer.get("hazard"):
        out += rect(W - PAD - STRIP, y, STRIP, h, style["hazards"][layer["hazard"]]["color"])
    rows = _label_rows(layer["label"])
    first = y + h / 2 + 8 - (len(rows) - 1) * LINE / 2
    return out + text(PAD + STRIP + 6, first, str(number), "#0F1419", weight=700) + lines(PAD + STRIP + 26, first, rows, "#0F1419", weight=600)


def _casing(data: Mapping[str, Any], tops: Sequence[float], style: Mapping[str, Any]) -> str:
    strings = data["strings"]
    mud, steel, cement = style["fluids"]["mud"]["color"], style["wellbore"]["steel"]["color"], style["wellbore"]["cement"]["color"]
    out, previous = "", tops[0]
    for i, string in enumerate(strings):
        half = OUTER - i * STEP
        shoe = _at(tops, string["shoe"], SHOE_AT)
        head = max(tops[0], previous - OVERLAP) if string["kind"] == "liner" else tops[0]
        out += rect(AXIS - half - RING, head, 2 * (half + RING), shoe - head, mud)
        if string["cement"] != "none":
            lift = head if string["cement"] == "full" else max(head, previous - OVERLAP if i else tops[0] + (shoe - tops[0]) / 2)
            out += _band(half + RING, half, lift, shoe, cement)
        out += _band(half, half - WALL, head, shoe, steel)
        out += "".join(path([(AXIS + k * half, shoe - 12), (AXIS + k * half, shoe), (AXIS + k * (half + 12), shoe)], style["background"], 1, fill=steel, closed=True)
                       for k in (-1, 1))
        x = AXIS + half + RING + 16
        out += rect(x - 11, shoe - 22, 24, 26, style["panel"], radius=5) + text(x + 1, shoe - 1, "АБВГД"[i], style["text"], "middle", 600)
        previous = shoe
    return out


def _hole(data: Mapping[str, Any], tops: Sequence[float], style: Mapping[str, Any]) -> str:
    strings = data["strings"]
    inner = OUTER - (len(strings) - 1) * STEP - WALL
    shoe = _at(tops, strings[-1]["shoe"], SHOE_AT)
    out = ""
    if data["bottom"]:
        end = _at(tops, data["bottom"], BOTTOM_AT)
        out += rect(AXIS - inner, shoe, 2 * inner, end - shoe, style["fluids"]["mud"]["color"])
        out += line(AXIS - inner, end, AXIS + inner, end, style["background"], 3)
        out += _drillstring(inner, tops[0], end, style) if data["drilling"] else ""
    if data["perforated"]:
        half = inner + WALL
        for share in (0.15, 0.35, 0.55):
            y = _at(tops, data["perforated"], share)
            out += "".join(line(AXIS + k * (half - WALL - 2), y, AXIS + k * (half + RING + 22), y, style["background"], 5) for k in (-1, 1))
    return out


def _drillstring(inner: float, top: float, end: float, style: Mapping[str, Any]) -> str:
    pipe, flow = style["wellbore"]["drillpipe"]["color"], style["text"]
    half = max(4.0, inner * 0.28)
    side = (inner + half) / 2
    out = rect(AXIS - half, top, 2 * half, end - top - 14, pipe)
    out += path([(AXIS - half, end - 22), (AXIS + half, end - 22), (AXIS + inner - 2, end - 10), (AXIS, end - 1), (AXIS - inner + 2, end - 10)], style["background"], 1, fill=pipe, closed=True)
    out += arrow(AXIS, top + 14, AXIS, top + 54, "#0F1419", 3, min(half, 8))
    return out + "".join(arrow(AXIS + k * side, end - 40, AXIS + k * side, end - 84, flow, 2, min((inner - half) / 2, 7)) for k in (-1, 1))


def _legend_items(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[tuple[str, str]]:
    wellbore, strings = style["wellbore"], data["strings"]
    items = [(wellbore["steel"]["color"], f"{'АБВГД'[i]} — {NAMES[s['kind']]}") for i, s in enumerate(strings)]
    items += [(wellbore["cement"]["color"], "цемент за колонной")] if any(s["cement"] != "none" for s in strings) else []
    items += [(style["fluids"]["mud"]["color"], "раствор в стволе")] if data["drilling"] or data["bottom"] else [(style["fluids"]["mud"]["color"], "жидкость в стволе")]
    items += [(wellbore["drillpipe"]["color"], "бурильная колонна; раствор идёт внутри вниз, снаружи вверх")] if data["drilling"] else []
    items += [(style["background"], "перфорация: каналы из колонны в пласт")] if data["perforated"] else []
    items += [(style["fluids"][f]["color"], f"{style['fluids'][f]['ru']} в порах (полоса слева)") for f in ("gas", "oil", "water") if any(x.get("fluid") == f for x in data["layers"])]
    return items + [(style["hazards"][h]["color"], f"{style['hazards'][h]['ru']} (полоса справа)") for h in HAZARDS if any(x.get("hazard") == h for x in data["layers"])]
