"""Поровое пространство: зёрна, глина, трещины или каверны, флюид и связанная вода."""

import math
from collections.abc import Mapping
from typing import Any

from glava.scenes.canvas import FONT, LINE, PAD, W, legend, lines, path, rect, wrap

LABEL = "схема"
FRAME_CLASS = "B"
SUMMARY = """grains — порода под увеличением: где находятся поры, глина и флюид. data: {"pores":"intergranular|fracture|cavernous","clay":"none|dispersed|laminated","fluid":"gas|oil|water","water_film":true|false}. dispersed — глина в порах, laminated — прослоями; water_film — плёнка связанной воды на зёрнах. Для fracture и cavernous порода плотная, clay: none."""
SCHEMA = {
    "type": "object", "required": ["pores", "clay", "fluid", "water_film"], "additionalProperties": False,
    "properties": {"pores": {"enum": ["intergranular", "fracture", "cavernous"]}, "clay": {"enum": ["none", "dispersed", "laminated"]},
                   "fluid": {"enum": ["gas", "oil", "water"]}, "water_film": {"type": "boolean"}},
}
HEIGHT, RADIUS = 270, 34
CAVERNS = ((0.2, 0.3, 46), (0.52, 0.62, 60), (0.82, 0.28, 38), (0.83, 0.78, 34), (0.22, 0.8, 30))
FRACTURES = (((0.0, 0.25), (0.3, 0.35), (0.6, 0.22), (1.0, 0.4)), ((0.1, 1.0), (0.35, 0.7), (0.5, 0.45), (0.75, 0.0)), ((0.45, 1.0), (0.7, 0.75), (1.0, 0.8)))


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    if data["pores"] != "intergranular" and data["clay"] != "none":
        return ["глина показывается только между зёрнами"]
    if data["fluid"] == "water" and data["water_film"]:
        return ["плёнка воды видна только рядом с нефтью или газом"]
    return []


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    fluid, sand, shale = style["fluids"][data["fluid"]], style["lithology"]["sand"], style["lithology"]["shale"]
    body = f'<defs><clipPath id="view"><rect x="{PAD}" y="{PAD}" width="{W - 2 * PAD}" height="{HEIGHT}"/></clipPath></defs><g clip-path="url(#view)">'
    if data["pores"] == "intergranular":
        body += rect(PAD, PAD, W - 2 * PAD, HEIGHT, fluid["color"]) + _grains(data, style)
        items = [(sand["color"], "зёрна породы"), (fluid["color"], f"{fluid['ru']} в порах")]
        items += [(shale["color"], "глина в порах" if data["clay"] == "dispersed" else "прослой глины")] if data["clay"] != "none" else []
    else:
        rock = style["lithology"]["limestone"]
        body += rect(PAD, PAD, W - 2 * PAD, HEIGHT, rock["color"]) + _voids(data, style)
        items = [(rock["color"], "плотный скелет породы"), (fluid["color"], f"{fluid['ru']} в {'трещинах' if data['pores'] == 'fracture' else 'кавернах'}")]
    items += [(style["fluids"]["water"]["color"], "плёнка связанной воды")] if data["water_film"] else []
    drawn, y = legend(items, PAD + HEIGHT + 12, style["text"])
    note = wrap("Увеличено во много раз, размеры условны", W - 2 * PAD)
    return body + "</g>" + drawn + lines(PAD, y + FONT, note, style["muted"]), y + LINE * len(note) + 8


def _grains(data: Mapping[str, Any], style: Mapping[str, Any]) -> str:
    film = f'stroke="{style["fluids"]["water"]["color"]}" stroke-width="6"' if data["water_film"] else 'stroke="#0F1419" stroke-width="1"'
    shale = style["lithology"]["shale"]["color"]
    step, rise = RADIUS * 2.04, RADIUS * 2.04 * math.sin(math.pi / 3)
    out = ""
    for row in range(int(HEIGHT // rise) + 3):
        y = PAD + row * rise
        for col in range(-1, int((W - 2 * PAD) // step) + 2):
            x = PAD + col * step + (row % 2) * step / 2
            if data["clay"] == "dispersed" and (row + col) % 2 == 0:
                out += f'<circle cx="{x + step / 2:.1f}" cy="{y + rise / 3:.1f}" r="9" fill="{shale}"/>'
            out += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{RADIUS - 3}" fill="{style["lithology"]["sand"]["color"]}" {film}/>'
    if data["clay"] == "laminated":
        out += "".join(rect(PAD, PAD + HEIGHT * k, W - 2 * PAD, 38, shale) for k in (0.22, 0.66))
    return out


def _voids(data: Mapping[str, Any], style: Mapping[str, Any]) -> str:
    fluid = style["fluids"][data["fluid"]]["color"]
    film = style["fluids"]["water"]["color"] if data["water_film"] else "#0F1419"
    if data["pores"] == "cavernous":
        return "".join(f'<circle cx="{PAD + x * (W - 2 * PAD):.1f}" cy="{PAD + y * HEIGHT:.1f}" r="{r}" fill="{fluid}" stroke="{film}" stroke-width="5"/>'
                       for x, y, r in CAVERNS)
    tracks = [[(PAD + x * (W - 2 * PAD), PAD + y * HEIGHT) for x, y in f] for f in FRACTURES]
    return "".join(path(t, film, 16) for t in tracks) + "".join(path(t, fluid, 9) for t in tracks)
