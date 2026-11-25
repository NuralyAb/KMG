"""Шаблоны сцен: SVG строит код, физика и читаемость проверяются до рисования."""

import xml.etree.ElementTree as ET

import pytest
from glava.modules.drawing.formula import evaluate
from glava.modules.drawing.scenes import (
    load_style,
    load_templates,
    render,
    scene_issues,
    wrap,
)
from glava.shared import paths

DOMAIN = paths.workspace() / "domain" / "geology"
STYLE = load_style(DOMAIN)
TEMPLATES = load_templates(DOMAIN / "templates")

GOOD = {
    "flow": {"nodes": [{"id": "a", "text": "Кривая ГК", "kind": "data"}, {"id": "b", "text": "Показания низкие?", "kind": "choice"},
                       {"id": "c", "text": "Песчаник", "kind": "result"}, {"id": "d", "text": "Глина", "kind": "result"}],
             "edges": [{"from": "a", "to": "b", "label": ""}, {"from": "b", "to": "c", "label": "да"}, {"from": "b", "to": "d", "label": "нет"}]},
    "compare": {"left_title": "Глина", "right_title": "Песчаник", "rows": [{"aspect": "Диаметр", "left": "увеличен", "right": "уменьшен"},
                                                                       {"aspect": "ГК", "left": "высокая", "right": "низкая"}]},
    "plot": {"x_label": "пористость", "y_label": "сопротивление", "numeric": False, "log_x": False, "log_y": False, "params": {},
             "series": [{"name": "вода", "color": "water", "points": [[0, 1], [0.5, 0.4], [1, 0.1]]}], "marks": []},
    "bars": {"unit": "%", "items": [{"name": "глина", "from": 5, "to": 20}, {"name": "песок", "from": 10, "to": 30}]},
    "log": {"layers": [{"lithology": "shale", "label": "глина", "thickness": 2}, {"lithology": "sand", "fluid": "oil", "label": "нефть", "thickness": 2},
                       {"lithology": "sand", "fluid": "water", "label": "вода", "thickness": 2}],
            "curves": [{"name": "GR", "levels": ["high", "low", "low"]}, {"name": "RES", "levels": ["low", "high", "low"]}], "filtrate": "fresh"},
    "section": {"shape": "anticline", "layers": [{"lithology": "shale", "label": "покрышка"}, {"lithology": "sand", "label": "пласт", "fluids": ["oil", "water"]},
                                                 {"lithology": "shale", "label": "глина"}], "wells": [{"x": 0.5, "label": "1"}]},
    "borehole": {"collector": True, "lithology": "sand", "fluid": "oil", "pressure": "mud_above", "bore": "mud", "cake": True},
    "grains": {"pores": "intergranular", "clay": "dispersed", "fluid": "oil", "water_film": True},
}


@pytest.mark.parametrize("name", sorted(GOOD))
def test_every_template_draws_valid_svg_with_label(name):
    assert scene_issues(TEMPLATES[name], GOOD[name], STYLE) == []

    svg = render(TEMPLATES[name], GOOD[name], STYLE)

    root = ET.fromstring(svg)
    texts = "".join(root.itertext())
    assert root.tag.endswith("svg")
    assert TEMPLATES[name].LABEL in texts
    sizes = {float(e.get("font-size")) for e in root.iter() if e.get("font-size")}
    assert min(sizes) >= 22


@pytest.mark.parametrize("name", sorted(GOOD))
def test_text_stays_inside_the_picture(name):
    root = ET.fromstring(render(TEMPLATES[name], GOOD[name], STYLE))
    height = float(root.get("viewBox").split()[3])
    for e in root.iter("{http://www.w3.org/2000/svg}text"):
        assert 0 <= float(e.get("x")) <= 480
        assert 0 <= float(e.get("y")) <= height


def broken(name, **patch):
    return scene_issues(TEMPLATES[name], {**GOOD[name], **patch}, STYLE)


def test_log_rejects_shale_with_lowest_gamma():
    assert broken("log", curves=[{"name": "GR", "levels": ["low", "high", "high"]}])


def test_log_rejects_water_more_resistive_than_oil():
    assert broken("log", curves=[{"name": "RES", "levels": ["low", "low", "high"]}])


def test_log_rejects_water_above_oil():
    layers = GOOD["log"]["layers"]
    assert any("под" in i or "над" in i for i in broken("log", layers=[layers[0], layers[2], layers[1]]))


def test_log_rejects_narrow_hole_in_shale():
    assert broken("log", curves=[{"name": "CALIPER", "levels": ["low", "low", "low"]}])


def test_log_rejects_wrong_number_of_levels():
    assert broken("log", curves=[{"name": "GR", "levels": ["high"]}])


def test_section_rejects_fluids_out_of_order():
    layers = GOOD["section"]["layers"]
    assert broken("section", layers=[layers[0], {**layers[1], "fluids": ["water", "oil"]}, layers[2]])


def test_section_rejects_hydrocarbons_without_seal():
    layers = GOOD["section"]["layers"]
    assert broken("section", layers=[{"lithology": "sand", "label": "песок"}, layers[1], layers[2]])


def test_borehole_rejects_invasion_into_non_collector():
    assert broken("borehole", collector=False, lithology="shale", fluid="oil")


def test_flow_rejects_cycles_and_unknown_nodes():
    assert broken("flow", edges=[{"from": "a", "to": "b", "label": ""}, {"from": "b", "to": "a", "label": ""}])
    assert broken("flow", edges=[{"from": "a", "to": "zzz", "label": ""}])


def test_schema_violation_is_reported():
    assert broken("bars", items=[])


def test_wrap_keeps_lines_short():
    lines = wrap("нефтегазонасыщенность коллектора определяют количественно", 180)
    assert all(len(line) * 12 <= 190 for line in lines)
    assert "".join(lines).replace("-", "").replace(" ", "").startswith("нефтегазонасыщенность")


def test_formula_is_calculated_without_python_access():
    assert evaluate("a * x ** (-m)", {"a": 1, "m": 2, "x": 0.5}) == 4
    with pytest.raises(ValueError):
        evaluate("__import__('os')", {})
    with pytest.raises(ValueError):
        evaluate("x.real", {"x": 1})
    with pytest.raises(ValueError):
        evaluate("9 ** 9 ** 9 ** 9", {})


def test_depth_must_grow_down():
    flat = {**GOOD["plot"], "x_label": "Глубина H"}
    assert scene_issues(TEMPLATES["plot"], flat, STYLE)
    down = {**GOOD["plot"], "x_label": "сопротивление", "y_label": "Глубина H", "y_down": True}
    assert scene_issues(TEMPLATES["plot"], down, STYLE) == []
    assert scene_issues(TEMPLATES["plot"], {**down, "y_down": False}, STYLE)


def test_penetration_depth_is_not_a_depth_axis():
    assert broken("plot", y_label="Глубина проникновения фильтрата") == []


def test_mark_must_sit_on_a_curve():
    assert broken("plot", marks=[{"x": 0.5, "y": 0.9, "text": "висит"}])
    assert broken("plot", marks=[{"x": 0.5, "y": 0.4, "text": "на кривой"}]) == []


def test_side_labels_of_a_branch_must_fit_together():
    edges = [{"from": "a", "to": "b", "label": ""}, {"from": "b", "to": "c", "label": "простые задачи"}, {"from": "b", "to": "d", "label": "сложные"}]
    assert broken("flow", edges=edges)


def test_cake_needs_mud_and_invasion():
    assert broken("borehole", bore="water", cake=True)
    assert broken("borehole", bore="water", cake=False) == []
    assert broken("borehole", pressure="mud_below", cake=True)


def test_thin_layer_keeps_its_whole_label():
    layers = [{**x, "thickness": 1, "label": "очень длинная подпись"[:20]} for x in GOOD["log"]["layers"]]
    assert broken("log", layers=layers)


def test_labels_of_arrows_into_one_block_must_fit_together():
    nodes = [{"id": k, "text": f"блок {k}", "kind": "step"} for k in "abc"]
    edges = [{"from": "a", "to": "c", "label": "числитель"}, {"from": "b", "to": "c", "label": "знаменатель"}]
    assert broken("flow", nodes=nodes, edges=edges)
