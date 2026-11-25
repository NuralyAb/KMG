"""Доменный пакет бурения: файлы на месте, таблицы читаются, цвета не спорят с флюидами, шаблоны проверяют физику и рисуют."""

import ast
import json
import re
import xml.etree.ElementTree as ET
from itertools import combinations
from typing import Any

import pytest
from glava.modules.drawing.api import load_style, load_templates, render, scene_issues
from glava.modules.illustrations.generator import illustration_issues
from glava.modules.library.service import domain_names
from glava.modules.video.speech import dictionaries, spoken
from glava.shared import paths

ROOT = paths.workspace()
DOMAIN = ROOT / "domain" / "drilling"
FILES = ("README.md", "audience.md", "axes.json", "difficulty.md", "glossary.md", "it_bridges.md", "misconceptions.json", "now_practice.md",
         "physics_checklist.json", "pronunciation.md", "stress_dictionary.md", "styleguide.json")
ACUTE = "́"
VOWELS = set("аеиоуыэюя")
TABLES = {"glossary.md": (4, 40, 70), "it_bridges.md": (4, 15, 40), "now_practice.md": (3, 15, 60), "stress_dictionary.md": (2, 120, 400)}
STYLE_PATH = re.compile(r'style\["(\w+)"\](?:\["(\w+)"\])?')
COLOR_GROUPS = ("lithology", "fluids", "curves", "wellbore", "hazards")
STYLE = load_style(DOMAIN)
TEMPLATES = load_templates(DOMAIN / "templates")
OWN = sorted(f.stem for f in (DOMAIN / "templates").glob("*.py"))


def read(name: str) -> str:
    return (DOMAIN / name).read_text(encoding="utf-8")


def rows(name: str) -> list[list[str]]:
    """Строки всех таблиц файла без заголовков и разделителей."""
    cells = [[c.strip() for c in line.strip().removeprefix("|").removesuffix("|").split("|")] for line in read(name).splitlines() if line.startswith("|")]
    rulers = {i for i, row in enumerate(cells) if set("".join(row)) <= set("-: ")}
    return [row for i, row in enumerate(cells) if i not in rulers and i + 1 not in rulers]


def repeated(values: list[str]) -> set[str]:
    return {v for v in values if values.count(v) > 1}


def enum_values(schema: dict[str, Any]) -> set[str]:
    own = {v for v in schema.get("enum", []) if isinstance(v, str)}
    nested = [*schema.get("properties", {}).values(), *([schema["items"]] if "items" in schema else [])]
    return own.union(*(enum_values(s) for s in nested))


def distance(a: str, b: str) -> float:
    return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (1, 3, 5)) ** 0.5


def layer(lithology: str, label: str, thickness: int = 1, **extra: str) -> dict[str, Any]:
    return {"lithology": lithology, "label": label, "thickness": thickness, **extra}


def string(kind: str, shoe: int, cement: str = "full") -> dict[str, Any]:
    return {"kind": kind, "shoe": shoe, "cement": cement}


def level(label: str, pore: float, frac: float, thickness: int = 2) -> dict[str, Any]:
    return {"label": label, "thickness": thickness, "pore": pore, "frac": frac}


LAYERS = [layer("sand", "рыхлые пески", hazard="unstable"), layer("shale", "глины", 2), layer("limestone", "трещины", hazard="loss"),
          layer("dense", "плотные"), layer("shale", "глины под давлением", 2, hazard="kick"), layer("sand", "пласт", 2, fluid="oil")]
WELL = {"layers": LAYERS, "strings": [string("conductor", 2), string("surface", 4), string("production", 6, "part")],
        "bottom": None, "drilling": False, "perforated": 6}
DRILLING = {"layers": LAYERS, "strings": [string("surface", 2), string("intermediate", 4, "part")], "bottom": 6, "drilling": True, "perforated": None}
LINER = {"layers": [layer("sand", "пески"), layer("shale", "глины"), layer("dense", "плотные"), layer("shale", "глины"), layer("sand", "пласт")],
         "strings": [string("conductor", 1), string("surface", 2), string("intermediate", 3), string("production", 4, "none"), string("liner", 5)],
         "bottom": 5, "drilling": False, "perforated": None}
MUD_LAYERS = [level("глины", 3, 5, 1), level("пески", 3, 5.5), level("зона АВПД", 6, 8), level("пласт", 5, 7.5, 1)]
WINDOW = {"axis": "density", "layers": MUD_LAYERS,
          "intervals": [{"to": 2, "mud": 4, "ecd": 4.6, "outcome": "window"}, {"to": 4, "mud": 6.6, "ecd": 7.1, "outcome": "window"}]}
ONE_MUD = {"axis": "density", "layers": MUD_LAYERS, "intervals": [{"to": 4, "mud": 5, "ecd": 5.4, "outcome": "both"}]}
GOOD = [("well", WELL), ("well", DRILLING), ("well", LINER), ("mudwindow", WINDOW), ("mudwindow", ONE_MUD), ("mudwindow", {**WINDOW, "axis": "pressure"})]


@pytest.mark.parametrize("name", FILES)
def test_pack_file_exists_and_is_not_empty(name):
    assert read(name).strip()


def test_pack_is_offered_to_the_library():
    assert "drilling" in domain_names(ROOT)


@pytest.mark.parametrize("name", TABLES)
def test_table_parses_without_empty_cells_and_repeats(name):
    width, least, most = TABLES[name]
    table = rows(name)
    assert least <= len(table) <= most
    assert [r for r in table if len(r) != width] == []
    assert [r for r in table if not all(r)] == []
    assert repeated([r[0].lower() for r in table]) == set()


def test_glossary_definition_is_short_and_has_english_term():
    assert [r[0] for r in rows("glossary.md") if len(r[1]) < 15 or len(re.findall(r"[.!?] [А-ЯЁ]", r[1])) > 1] == []
    assert [r[0] for r in rows("glossary.md") if not re.search(r"[a-z]{2}", r[2])] == []


def test_now_practice_states_confidence_and_names_no_numbers():
    assert {r[2] for r in rows("now_practice.md")} <= {"высокая", "средняя, проверить", "низкая"}
    assert [r for r in rows("now_practice.md") if re.search(r"\d", r[0] + r[1])] == []


def test_every_difficulty_type_of_the_node_schema_is_described():
    assert re.findall(r"^- (\w+) —", read("difficulty.md"), re.MULTILINE) == ["М", "В", "И", "Ф", "П", "Пр", "Н", "Р"]


def test_stress_marks_exactly_one_vowel_of_the_same_word():
    for word, marked in [*rows("stress_dictionary.md"), *(r for r in rows("pronunciation.md") if len(r) == 2)]:
        assert re.fullmatch(r"[а-я]+", word), word
        assert marked.count(ACUTE) == 1, word
        assert marked.replace(ACUTE, "") == word
        assert marked[marked.index(ACUTE) - 1] in VOWELS, word


def test_pronunciation_and_stress_work_in_speech_and_do_not_overlap():
    short, known = dictionaries(read("pronunciation.md"))
    none, extra = dictionaries(read("stress_dictionary.md"))
    assert none == {}
    assert len(extra) == len(rows("stress_dictionary.md"))
    assert len(short) == len([r for r in rows("pronunciation.md") if len(r) == 3])
    assert set(known) & set(extra) == set()
    assert spoken("КНБК и скважина", short, known) == "ка эн бэ ка и сква́жина"


def test_stress_dictionary_lists_words_to_check_by_ear():
    doubtful = read("stress_dictionary.md").split("## Проверить на слух")[1]
    assert len(re.findall(r"^- ", doubtful, re.MULTILINE)) >= 5


@pytest.mark.parametrize(("name", "prefix", "text_key", "least", "most"),
                         [("misconceptions.json", "misc.", "text", 12, 30), ("physics_checklist.json", "pc.", "item", 15, 40)])
def test_ids_are_unique_and_described(name, prefix, text_key, least, most):
    items = json.loads(read(name))
    assert least <= len(items) <= most
    assert repeated([i["id"] for i in items]) == set()
    assert [i for i in items if not i["id"].startswith(prefix) or not i[text_key].strip()] == []


def test_styleguide_keeps_keys_and_fluid_colors_of_geology():
    geology = load_style(ROOT / "domain" / "geology")
    assert set(geology) <= set(STYLE)
    assert {k: v["color"] for k, v in geology["fluids"].items() if k != "mud"}.items() <= {k: v["color"] for k, v in STYLE["fluids"].items()}.items()
    assert STYLE["provenance"] == geology["provenance"]


def test_colors_do_not_repeat_and_are_far_from_fluids():
    colors = {(group, key): v["color"] for group in COLOR_GROUPS for key, v in STYLE[group].items()}
    assert [(a, b) for a, b in combinations(colors, 2) if distance(colors[a], colors[b]) < 35] == []
    reservoir = [colors["fluids", k] for k in ("oil", "gas", "water")]
    assert [k for k, c in colors.items() if k[0] != "fluids" and min(distance(c, f) for f in reservoir) < 60] == []


def test_styleguide_has_every_key_named_in_templates():
    named = {match for f in (DOMAIN / "templates").glob("*.py") for match in STYLE_PATH.findall(f.read_text(encoding="utf-8"))}
    assert {top for top, _ in named} <= set(STYLE)
    assert {(top, key) for top, key in named if key and key not in STYLE[top]} == set()


def test_well_schema_allows_only_values_with_a_color():
    fields = TEMPLATES["well"].SCHEMA["properties"]["layers"]["items"]["properties"]
    assert set(fields["lithology"]["enum"]) == set(STYLE["lithology"])
    assert set(fields["fluid"]["enum"]) - {None} <= set(STYLE["fluids"])
    assert set(fields["hazard"]["enum"]) - {None} == set(STYLE["hazards"])


@pytest.mark.parametrize("name", OWN)
def test_template_imports_only_the_sdk(name):
    tree = ast.parse((DOMAIN / "templates" / f"{name}.py").read_text(encoding="utf-8"))
    found = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert {m for m in found if m.startswith("glava")} == {"glava.sdk.drawing"}
    assert found <= {"glava.sdk.drawing", "collections.abc", "typing"}


@pytest.mark.parametrize("name", OWN)
def test_template_contract(name):
    module = TEMPLATES[name]
    assert module.SUMMARY.startswith(f"{name} — ")
    assert module.LABEL in STYLE["provenance"]
    assert module.FRAME_CLASS in "ABCD"


@pytest.mark.parametrize("name", OWN)
def test_enum_values_have_no_signs_forbidden_in_scenes(name):
    """Движок не пускает в сцену строки с подчёркиванием: значение схемы с ним сделало бы шаблон недоступным."""
    assert {v for v in enum_values(TEMPLATES[name].SCHEMA) if set(v) & set("_$\\")} == set()


@pytest.mark.parametrize(("name", "data"), GOOD)
def test_template_draws_readable_svg(name, data):
    assert scene_issues(TEMPLATES[name], data, STYLE) == []

    root = ET.fromstring(render(TEMPLATES[name], data, STYLE))

    height = float(root.get("viewBox").split()[3])
    texts = list(root.iter("{http://www.w3.org/2000/svg}text"))
    assert TEMPLATES[name].LABEL in "".join(root.itertext())
    assert min(float(e.get("font-size")) for e in texts) >= 22
    for e in texts:
        width = len(e.text) * 12
        start = float(e.get("x")) - {"start": 0, "middle": width / 2, "end": width}[e.get("text-anchor")]
        assert 0 <= start and start + width <= 480, e.text
        assert 0 <= float(e.get("y")) <= height


@pytest.mark.parametrize(("name", "data"), GOOD)
def test_scene_passes_the_engine_check_without_numbers_in_claims(name, data):
    """Условные уровни и номера слоёв — не числа главы, движок не должен требовать их в утверждениях."""
    node = {"id": "d.n", "claims": [{"id": "d.n#c1", "text": "Колонна перекрывает зону АВПД", "quote": "колонна перекрывает зону"}]}
    scene = {"node_id": "d.n", "template": name, "caption": "Подпись", "alt": "Описание", "claim_ids": ["d.n#c1"], "data": data}
    assert illustration_issues({"illustrations": [scene]}, [node], TEMPLATES, STYLE) == []


def rejected(name: str, data: dict[str, Any], **patch: Any) -> str:
    return " ".join(scene_issues(TEMPLATES[name], {**data, **patch}, STYLE))


def test_well_rejects_next_string_not_deeper():
    assert "глубже" in rejected("well", WELL, strings=[string("conductor", 4), string("production", 4)])


def test_well_rejects_wrong_order_of_strings():
    assert "порядок" in rejected("well", WELL, strings=[string("production", 2), string("surface", 4)], perforated=None)


def test_well_rejects_liner_without_previous_string():
    assert "хвостовику" in rejected("well", WELL, strings=[string("liner", 6)], perforated=None)


def test_well_rejects_shoe_in_troubled_layer():
    assert "осложнённом" in rejected("well", WELL, strings=[string("surface", 3), string("production", 6)])


def test_well_rejects_fluid_in_non_reservoir():
    assert "флюид" in rejected("well", WELL, layers=[*LAYERS[:5], layer("shale", "глина", fluid="oil")], perforated=None)


@pytest.mark.parametrize("patch", [{"perforated": 2}, {"perforated": 3}, {"perforated": 6, "strings": [string("surface", 2), string("intermediate", 4)]},
                                   {"perforated": 6, "drilling": True, "bottom": 6}])
def test_well_rejects_wrong_perforation(patch):
    assert "перфор" in rejected("well", WELL, **patch)


def test_well_rejects_bottom_above_shoe_and_drilling_without_bottom():
    assert "забой" in rejected("well", DRILLING, bottom=3)
    assert "bottom" in rejected("well", DRILLING, bottom=None)


def test_well_rejects_unknown_layer_number():
    assert "номер слоя" in rejected("well", WELL, layers=LAYERS[:3])


def test_mudwindow_outcome_follows_from_levels():
    assert "из уровней следует" in rejected("mudwindow", WINDOW, intervals=[{"to": 4, "mud": 5, "ecd": None, "outcome": "window"}])
    assert rejected("mudwindow", WINDOW, intervals=[{"to": 4, "mud": 5, "ecd": None, "outcome": "kick"}]) == ""


def test_mudwindow_compares_all_open_layers_not_only_the_bottom():
    heavy = [{"to": 4, "mud": 6.6, "ecd": None, "outcome": "window"}]
    assert "loss" in rejected("mudwindow", WINDOW, intervals=heavy)


def test_mudwindow_rejects_frac_below_pore_and_light_circulation():
    assert "гидроразрыв" in rejected("mudwindow", WINDOW, layers=[level("глины", 6, 5), *MUD_LAYERS[1:]])
    assert "при циркуляции" in rejected("mudwindow", WINDOW, intervals=[{"to": 2, "mud": 4, "ecd": 3.5, "outcome": "window"}, WINDOW["intervals"][1]])


def test_mudwindow_intervals_cover_the_whole_section():
    assert "to растёт" in rejected("mudwindow", WINDOW, intervals=WINDOW["intervals"][:1])


def test_pressure_grows_with_depth_for_constant_density():
    """В осях давления линия раствора наклонена: то же значение плотности глубже даёт больше."""
    svg = render(TEMPLATES["mudwindow"], {**WINDOW, "axis": "pressure"}, STYLE)
    mud = [p for p in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}path") if p.get("stroke") == STYLE["curves"]["MUD"]["color"]]
    for drawn in mud:
        (x1, y1), (x2, y2) = [tuple(map(float, p.split(","))) for p in drawn.get("d")[1:].split(" L")]
        assert y2 > y1 and x2 > x1


@pytest.mark.parametrize("label", ["Глубина по стволу, м", "Вертикальная глубина", "Measured depth, m", "TVD, m", "Depth"])
def test_well_depth_grows_down(label):
    data = {"x_label": "время", "y_label": label, "numeric": False, "series": [{"name": "ход", "points": [[0, 0], [1, 1]]}]}
    assert scene_issues(TEMPLATES["plot"], data, STYLE)
    assert scene_issues(TEMPLATES["plot"], {**data, "y_down": True}, STYLE) == []


@pytest.mark.parametrize("label", ["Глубина внедрения зуба", "Глубина резания", "Depth of cut, mm", "Механическая скорость"])
def test_other_depths_are_not_well_depth(label):
    data = {"x_label": "нагрузка", "y_label": label, "numeric": False, "series": [{"name": "ход", "points": [[0, 0], [1, 1]]}]}
    assert scene_issues(TEMPLATES["plot"], data, STYLE) == []
