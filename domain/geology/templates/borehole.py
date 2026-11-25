"""Прискважинная зона: раствор, корка, фильтрат, нетронутый пласт. Направление потока — от высокого давления к низкому."""

from collections.abc import Mapping
from typing import Any

from glava.scenes.canvas import FONT, LINE, PAD, W, arrow, legend, line, lines, rect, text, wrap

LABEL = "схема"
FRAME_CLASS = "B"
SUMMARY = """borehole — скважина и прискважинная зона: раствор, глинистая корка, зона проникновения фильтрата, нетронутый пласт. data: {"collector":true|false,"lithology":"sand|shale|limestone|dolomite|reef|dense|salt|anhydrite","fluid":"gas|oil|water"(только у коллектора),"pressure":"mud_above|mud_below","bore":"mud|water|oil_mud","cake":true|false}. bore — чем заполнен ствол: глинистый раствор, вода или нефильтрующийся раствор; cake — есть ли глинистая корка (только при глинистом растворе и фильтрации в коллектор). mud_above: давление раствора выше пластового, фильтрат идёт в пласт; mud_below: приток из пласта в скважину."""
SCHEMA = {
    "type": "object", "required": ["collector", "lithology", "pressure", "bore", "cake"], "additionalProperties": False,
    "properties": {"collector": {"type": "boolean"}, "lithology": {"enum": ["sand", "shale", "limestone", "dolomite", "reef", "dense", "salt", "anhydrite"]},
                   "fluid": {"enum": ["gas", "oil", "water", None]}, "pressure": {"enum": ["mud_above", "mud_below"]},
                   "bore": {"enum": ["mud", "water", "oil_mud"]}, "cake": {"type": "boolean"}},
}
NOT_RESERVOIR = {"shale", "salt", "anhydrite", "dense"}
BORES = {"mud": ("mud", "глинистый раствор в стволе"), "water": ("filtrate", "вода в стволе"), "oil_mud": ("mud", "нефильтрующийся раствор в стволе")}
HEIGHT = 230
BORE, CAKE, INVADED = 110, 16, 150


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    if data["collector"] and data["lithology"] in NOT_RESERVOIR:
        return ["эта порода не коллектор: корки и проникновения в неё нет"]
    if data["cake"] and (not data["collector"] or data["bore"] != "mud" or data["pressure"] != "mud_above"):
        return ["корка бывает только при глинистом растворе и фильтрации в коллектор"]
    if data["collector"] and not data.get("fluid"):
        return ["у коллектора укажите флюид пласта"]
    if not data["collector"] and data.get("fluid"):
        return ["в неколлекторе подвижного флюида и проникновения нет"]
    return []


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    mud_above, collector = data["pressure"] == "mud_above", data["collector"]
    top = float(PAD)
    edge = PAD + BORE
    rock = style["lithology"][data["lithology"]]
    bore_key, bore_name = BORES[data["bore"]]
    bore_color = style["fluids"][bore_key]["color"]
    invades = mud_above and data["bore"] != "oil_mud"
    body = rect(PAD, top, BORE, HEIGHT, bore_color)
    body += rect(edge, top, W - PAD - edge, HEIGHT, rock["color"])
    items = [(bore_color, bore_name), (rock["color"], rock["ru"])]
    if collector:
        fluid = style["fluids"][data["fluid"]]
        start = edge + (INVADED if invades else 0)
        body += _pores(start, top, W - PAD, fluid["color"])
        items += [(fluid["color"], f"{fluid['ru']} в порах пласта")]
        if invades:
            filtrate = style["fluids"]["filtrate"]
            body += _pores(edge + CAKE, top, start, filtrate["color"])
            body += line(start, top, start, top + HEIGHT, style["background"], 3, "8 6")
            items += [(filtrate["color"], "зона проникновения: фильтрат в порах")]
            if data["cake"]:
                body += rect(edge - CAKE, top, CAKE, HEIGHT, style["lithology"]["shale"]["color"])
                items += [(style["lithology"]["shale"]["color"], "глинистая корка на стенке")]
        ends = (edge - 60, edge + 90) if mud_above else (edge + 90, edge - 60)
        body += "" if mud_above and not invades else "".join(arrow(ends[0], top + k * HEIGHT, ends[1], top + k * HEIGHT, "#0F1419", 5, 12) for k in (0.3, 0.7))
    body += line(edge, top, edge, top + HEIGHT, style["background"], 2)
    body += text(PAD + 8, top + FONT + 4, "ствол", style["text"], weight=600)
    body += text(W - PAD - 8, top + FONT + 4, "пласт", "#0F1419", "end", 600)
    drawn, y = legend(items, top + HEIGHT + 12, style["text"])
    sign = "выше" if mud_above else "ниже"
    tail = "" if collector and (invades or not mud_above) else " Проникновения нет." if collector else " Порода не пропускает фильтрат: корки и проникновения нет."
    note = wrap(f"Давление в стволе {sign} пластового.{tail} Без масштаба", W - 2 * PAD)
    return body + drawn + lines(PAD, y + FONT, note, style["muted"]), y + LINE * len(note) + 8


def _pores(x1: float, top: float, x2: float, color: str) -> str:
    """Флюид — капли в порах, а не сплошной слой."""
    step = 22
    out = ""
    for row in range(int(HEIGHT // step)):
        x = x1 + 8 + (row % 2) * step / 2
        while x < x2 - 6:
            out += f'<circle cx="{x:.1f}" cy="{top + 12 + row * step:.1f}" r="5" fill="{color}" stroke="#0F1419" stroke-width="1"/>'
            x += step
    return out
