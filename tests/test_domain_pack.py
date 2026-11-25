"""Доменный пакет геологии: файлы на месте, таблицы читаются, словари согласованы между собой и с шаблонами."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from glava.scenes import load_style, load_templates
from glava.video.speech import dictionaries, spoken

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "domain" / "geology"
FILES = ("README.md", "audience.md", "axes.json", "difficulty.md", "glossary.md", "it_bridges.md", "misconceptions.json", "now_practice.md",
         "physics_checklist.json", "pronunciation.md", "stress_dictionary.md", "styleguide.json")
FOLDERS = ("errata", "templates", "video")
ACUTE = "́"
VOWELS = set("аеиоуыэюя")
TABLES = {"glossary.md": (5, 90, 150), "it_bridges.md": (4, 25, 40), "now_practice.md": (3, 15, 60), "stress_dictionary.md": (2, 120, 400)}
BOOKS = {"Латышова": "latyshova_gl5_par17-20", "Басниев": "basniev_gl23-24_1", "Кузнецов": "kuznetsov_gl10",
         "Вендельштейн": "vendelshtein_gl1", "Баренблатт": "barenblatt_par4", "Барабошкин": "baraboshkin_par1-2"}
STYLE_GROUPS = {"lithology": "lithology", "fluid": "fluids", "fluids": "fluids", "name": "curves"}
STYLE_PATH = re.compile(r'style\["(\w+)"\](?:\["(\w+)"\])?')


def read(name: str) -> str:
    return (DOMAIN / name).read_text(encoding="utf-8")


def rows(name: str) -> list[list[str]]:
    """Строки всех таблиц файла без заголовков и разделителей."""
    cells = [[c.strip() for c in line.strip().removeprefix("|").removesuffix("|").split("|")] for line in read(name).splitlines() if line.startswith("|")]
    rulers = {i for i, row in enumerate(cells) if set("".join(row)) <= set("-: ")}
    return [row for i, row in enumerate(cells) if i not in rulers and i + 1 not in rulers]


def repeated(values: list[str]) -> set[str]:
    return {v for v in values if values.count(v) > 1}


def allowed_values(schema: dict[str, Any], key: str = "") -> set[tuple[str, str]]:
    """Пары «группа стайлгайда, ключ», которые схема шаблона разрешает модели."""
    own = {(STYLE_GROUPS[key], v) for v in schema.get("enum", []) if key in STYLE_GROUPS and v is not None}
    nested = [(name, s) for name, s in schema.get("properties", {}).items()] + ([(key, schema["items"])] if "items" in schema else [])
    return own.union(*(allowed_values(s, name) for name, s in nested))


@pytest.mark.parametrize("name", FILES)
def test_pack_file_exists_and_is_not_empty(name):
    assert read(name).strip()


@pytest.mark.parametrize("name", FOLDERS)
def test_pack_folder_is_not_empty(name):
    if name == "errata" and not (DOMAIN / name).exists():
        pytest.skip("листы опечаток содержат текст глав и в CI не выгружаются")
    assert any(f.is_file() for f in (DOMAIN / name).iterdir())


@pytest.mark.parametrize("name", TABLES)
def test_table_parses_without_empty_cells_and_repeats(name):
    width, least, most = TABLES[name]
    table = rows(name)
    assert least <= len(table) <= most
    assert [r for r in table if len(r) != width] == []
    assert [r for r in table if not all(r)] == []
    assert repeated([r[0].lower() for r in table]) == set()


def test_glossary_definition_is_short():
    """Одна фраза и, самое большее, одна оговорка о расхождении школ."""
    assert [r[0] for r in rows("glossary.md") if len(r[1]) < 15 or len(re.findall(r"[.!?] [А-ЯЁ]", r[1])) > 1] == []


def test_glossary_cites_only_pages_of_the_chapters():
    chapters = json.loads((ROOT / "chapters.json").read_text(encoding="utf-8"))["chapters"]
    allowed = {book: {p for first, last in chapters[key]["pages"] for p in range(first, last + 1)} for book, key in BOOKS.items()}
    cited = [(r[0], *part.strip().split(", ")) for r in rows("glossary.md") for part in r[4].split(";")]
    assert [c for c in cited if c[1] not in allowed or len(c) < 3] == []
    assert [c for c in cited if not {int(p) for p in c[2:]} <= allowed[c[1]]] == []
    assert {c[1] for c in cited} == set(BOOKS)


def test_now_practice_states_confidence():
    assert {r[2] for r in rows("now_practice.md")} <= {"высокая", "средняя, проверить"}


def test_stress_marks_exactly_one_vowel_of_the_same_word():
    for word, marked in rows("stress_dictionary.md"):
        assert re.fullmatch(r"[а-я]+", word), word
        assert marked.count(ACUTE) == 1, word
        assert marked.replace(ACUTE, "") == word
        assert marked[marked.index(ACUTE) - 1] in VOWELS, word


def test_stress_dictionary_does_not_repeat_pronunciation_and_works_in_speech():
    _, known = dictionaries(read("pronunciation.md"))
    short, extra = dictionaries(read("stress_dictionary.md"))
    assert short == {}
    assert len(extra) == len(rows("stress_dictionary.md"))
    assert set(known) & set(extra) == set()
    assert spoken("Коллекторы и поры", {}, extra) == "Колле́кторы и поры"


def test_stress_dictionary_lists_words_to_check_by_ear():
    assert len(re.findall(r"^- ", read("stress_dictionary.md").split("## Проверить на слух")[1], re.MULTILINE)) >= 5


@pytest.mark.parametrize(("name", "prefix", "text_key"), [("misconceptions.json", "misc.", "text"), ("physics_checklist.json", "pc.", "item")])
def test_ids_are_unique_and_described(name, prefix, text_key):
    items = json.loads(read(name))
    assert repeated([i["id"] for i in items]) == set()
    assert [i for i in items if not i["id"].startswith(prefix) or not i[text_key].strip()] == []


def test_styleguide_has_every_key_named_in_templates():
    style = load_style(DOMAIN)
    sources = [f.read_text(encoding="utf-8") for folder in ("templates", "video") for f in (DOMAIN / folder).glob("*.py")]
    named = {match for source in sources for match in STYLE_PATH.findall(source)}
    assert {top for top, _ in named} <= set(style)
    assert {(top, key) for top, key in named if key and key not in style[top]} == set()


def test_styleguide_has_every_value_allowed_by_template_schemas():
    style = load_style(DOMAIN)
    templates = {name: module for name, module in load_templates(DOMAIN / "templates").items() if (DOMAIN / "templates" / f"{name}.py").exists()}
    used = {pair for module in templates.values() for pair in allowed_values(module.SCHEMA)}
    assert {group for group, _ in used} == {"lithology", "fluids", "curves"}
    assert {(group, value) for group, value in used if value not in style[group]} == set()
    assert {module.LABEL for module in templates.values()} <= set(style["provenance"])
