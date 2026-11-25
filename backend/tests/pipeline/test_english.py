"""Английская глава проходит конвейер без модели, а запросы по русской не меняются ни на байт."""

import hashlib
import json
import logging

import pytest
from english_sample import MD, RANGES, Model, node_answer, plan_for, said
from glava.modules.layer.builder import make_node, plan_issues
from glava.modules.library.extract import decoded
from glava.modules.library.registry import LibraryError
from glava.modules.source_text.blocks import book_tables
from glava.modules.source_text.units import (
    Unit,
    is_english_source,
    parse_units,
    read_pages,
)
from glava.modules.tasks.generator import task_issues
from glava.modules.trust.audit import audit_layer, claim_flags, early_terms
from glava.modules.trust.mutate import measure
from glava.pipeline.chapter import Chapter, load_chapter
from glava.pipeline.prompts import FOLDER, prompt_file
from glava.pipeline.steps.course import build_site
from glava.pipeline.steps.layer import build_layer
from glava.shared import paths
from glava.shared.evidence import (
    bare_term,
    numbers_in,
    quote_on_page,
    restored_quote,
    term_order_issues,
    unsupported_numbers,
    verify_layer,
)
from glava.shared.json_files import read, save
from glava.shared.language import has_english, is_english, is_untranslated

PAGES = read_pages(MD, RANGES)
UNITS = parse_units(PAGES)


def kind_of(start: str) -> str:
    return next(u.kind for u in UNITS if u.text.startswith(start))


# ---------- единицы
@pytest.mark.parametrize(("start", "kind"), [
    ("# 3.1", "heading"), ("The column", "paragraph"), ("Figure 3.1 shows", "paragraph"), ("$$p", "formula"), ("Figure 3.1. Pressure", "figure"), ("━━━", "figure"),
    ("Table 3.1", "table"), ("**Example", "worked_example"), ("Solution", "worked_example"), ("## Review", "heading"), ("3.1 Why", "task"), ("3.2 A gauge", "task"), ("## References", "heading"),
])
def test_unit_kinds(start, kind):
    assert kind_of(start) == kind


def test_running_titles_and_references_may_be_skipped_but_nothing_else():
    skippable = [u.text.split()[0] for u in UNITS if u.skippable]
    assert skippable == ["Chapter", "Chapter", "Chapter", "Smith,", "Chapter", "Green,"]


def test_no_text_is_lost():
    joined = "".join("".join(u.text for u in UNITS).split())
    assert joined == "".join("".join(PAGES.values()).split()).replace("----", "")
    assert len({u.unit_id for u in UNITS}) == len(UNITS)


@pytest.mark.parametrize(("heading", "item", "kind"), [
    ("Problems", "4-1. Find the pressure at the bottom of the well.", "task"), ("## 4.8 Problems", "(2) Find the pressure at the bottom of the well.", "task"),
    ("### Problem 4.1", "A well is drilled to the top of the sand and is logged.", "task"), ("## Chapter 4 Exercises", "**4.12** Find the pressure in the well.", "task"),
    ("## Example 4.2", "A well is drilled to the top of the sand and is logged.", "worked_example"), ("# Fluid flow", "1. The fluid is water and the flow is steady in the sand.", "paragraph"),
])
def test_task_sections_are_recognised(heading, item, kind):
    units = parse_units({1: f"The text of the chapter is in English and it is about the flow of fluids.\n\n{heading}\n\n{item}"})
    assert [u.kind for u in units][1:] == ["heading", kind]


def test_heading_without_a_blank_line_does_not_swallow_the_paragraph():
    units = parse_units({1: "# Flow\nThe flow of the fluid is steady and it is in the sand."})
    assert [u.kind for u in units] == ["heading", "paragraph"]


def test_table_under_its_caption_reaches_the_course():
    table = next(u for u in UNITS if u.kind == "table")
    found = book_tables({"unit_ids": [table.unit_id]}, UNITS, [])[0]
    assert found["header"][2] == "Depth limit, ft" and found["rows"][0][2] == "12,500"


def test_language_is_decided_by_prose():
    russian_ocr = "OchoBbAcb Ha pe3yIbTaTax peHHeHH npeIbIyIeH 3aJaH, BbUHcJIHTb, KaKa OIIb6a"
    assert is_english_source(UNITS) and not is_english_source([Unit("p1", "paragraph", 1, "Пласт NaCl, BK-3, $\\mathrm{in} = \\mathrm{the}$")])
    assert not is_english(russian_ocr) and not has_english(russian_ocr) and not is_english("\\mathrm{h} _ {\\mathrm{sp}} \\Sigma = \\mathrm{h}")
    assert has_english(PAGES[11]) and is_english("Porosity is the ratio of two volumes")


# ---------- числа
@pytest.mark.parametrize(("text", "source"), [
    ("1250 футов", "is 1,250 ft in the well"), ("1 250 000 футов", "is 1,250,000 ft of the pipe"), ("0,25", "the value of .25 is in the table"), ("0,5 и 12,5", "the 0.5 and 12.50 of it"),
    ("1,5·10³", "of the order 1.5×10³ in it"), ("1,5·10³", "it is 1.5E3 of the total"), ("2·10⁻³", "the value is 2x10-3 in it"), ("1250", "it is $1{,}250$ in the well"), ("0,7", "the ratio is 0·7 in it"),
    ("12 500", "the depth is 12 500 ft in it"),
])
def test_english_numbers_are_read(text, source):
    assert unsupported_numbers(text, source) == set()


@pytest.mark.parametrize(("text", "source"), [
    ("1,250 фута", "is 1,250 ft in the well"), ("25", "the value of .25 is in the table"), ("1251", "is 1,250 ft in the well"), ("1,5·10⁴ и 7", "of the order 1.5×10³ in it"),
])
def test_wrong_numbers_are_still_caught(text, source):
    assert unsupported_numbers(text, source)


def test_russian_numbers_are_read_as_before():
    assert unsupported_numbers("1250", "глубина 1,250 м") == numbers_in("1250") and not unsupported_numbers("1,25", "глубина 1,250 м")
    # русское описание рисунка на английской странице читается по-русски
    assert not unsupported_numbers("1,125", f"{PAGES[11]}\nОсь Y: до 1,125 м")


# ---------- цитаты
@pytest.mark.parametrize("quote", ["This is the driller's \"first barrier\".", "The permeability of the filter cake", "permeability of 1.5x10³ md"])
def test_quote_gets_the_look_of_the_page(quote):
    page = "\n".join(PAGES.values())
    assert quote_on_page(restored_quote(quote, page), page)


@pytest.mark.parametrize("quote", ["This is the driller's second barrier", "permeability of 1.6×10³ md", ""])
def test_changed_words_and_numbers_are_not_restored(quote):
    assert restored_quote(quote, PAGES[11] + PAGES[12]) is None


def test_russian_quote_is_never_restored():
    assert restored_quote('так называемый "пласт"', "так называемый «пласт»") is None


# ---------- термины
def test_term_with_its_original_is_one_term():
    assert bare_term("Пористость (porosity)") == "пористость" and bare_term("акустический метод (АК)") == "акустический метод (ак)"
    assert bare_term("зависимость Pн = f(kв)") == "зависимость pн = f(kв)"
    nodes = [{"id": "a", "order": 1, "terms_introduced": [], "terms_used": ["пористость"], "layers": {"main": said("Пористость важна.")}, "claims": []},
             {"id": "b", "order": 2, "terms_introduced": ["пористость (porosity)"], "terms_used": [], "layers": {}, "claims": []}]
    assert [i.code for i in term_order_issues(nodes)] == ["term_before_definition"] and early_terms(nodes)[0]["used_in"] == ["a"]
    plan = plan_for(UNITS)
    plan["nodes"].append({**plan["nodes"][0], "slug": "again", "terms_introduced": ["гидростатическое давление"]})
    assert any("объясняется в 2" in i for i in plan_issues(plan, UNITS))


# ---------- доверие: русское утверждение, английская цитата
QUOTE = "Permeability usually decreases as the clay content increases, and the limit of 12 % at 3,000 psi does not change in all sands"
GOOD = "Проницаемость обычно снижается с ростом глинистости, а порог 12 % при 3000 psi во всех песках не меняется"


def test_faithful_translation_is_not_flagged():
    assert claim_flags(GOOD, QUOTE) == []


@pytest.mark.parametrize(("text", "flag"), [
    (GOOD.replace("снижается", "повышается").replace("ростом", "снижением"), None), (GOOD.replace("снижается", "растёт"), "direction"), (GOOD.replace("3000", "3500"), "number"), (GOOD.replace("3000 psi", "3000 МПа"), "unit"),
    (GOOD.replace("не меняется", "меняется"), "negation"), (GOOD.replace("обычно ", ""), "condition"),
])
def test_damage_is_seen_through_the_translation(text, flag):
    # две перестановки сразу меняют местами причину и следствие: счётом слов это не увидеть, это дело второй модели
    assert (flag in claim_flags(text, QUOTE)) if flag else claim_flags(text, QUOTE) == []


@pytest.mark.parametrize(("text", "quote"), [
    ("Давление не зависит от диаметра.", "The pressure is independent of the diameter"), ("Флюид несжимаем.", "The fluid is incompressible in this case"),
    ("Глинистая корка всегда тоньше.", "The filter cake is always thinner in this case"), ("Приток возможен, если депрессия больше нуля.", "Inflow occurs only if the drawdown is greater than zero"),
    ("Толщина не более 5 футов.", "The thickness of the bed is no more than 5 ft"), ("Может давать 650 psi при градиенте 0,52 psi/фут.", "It may be 650 psi if the gradient is .52 psi/ft"),
    ("Глубина 12 м, доля 5 %.", "The depth is 12 m and the share is 5 %"), ("Никакой пласт не поглощает.", "No formation is able to take the mud"),
])
def test_ordinary_translations_are_not_flagged(text, quote):
    assert claim_flags(text, quote) == []


def test_lost_quantifier_word_is_seen():
    assert claim_flags("Всегда растёт.", "The pressure increases with the depth of the well") == ["quantifier"]


def test_check_is_not_blind_on_translated_claims():
    claims = [{"id": f"x#c{i}", "text": GOOD, "quote": QUOTE, "page_pdf": 1} for i in range(3)]
    found = measure(claims)
    assert found["flagged_originals"] == 0 and {k for k, v in found["kinds"].items() if v["caught"] == v["made"] > 0} >= {"number", "negation_removed", "lost_condition", "sign_flip"}


# ---------- слой и курс на подставной модели
@pytest.fixture
def chapter(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    domain = tmp_path / "domain" / "own"
    save(domain / "misconceptions.json", [])
    (domain / "difficulty.md").write_text("Типы трудности", encoding="utf-8")
    return Chapter("demo_en", "demo", "Pressure in a Wellbore", "Sample", domain, tuple(UNITS), "demo.md")


def test_english_chapter_is_built_into_a_russian_layer(chapter):
    model = Model(plan_for(UNITS))
    layer = build_layer(chapter, model)
    report = read(chapter.work / "layer_report.json")
    assert (report["issues"], report["dropped_claims"], report["not_enriched"]) == ({}, [], [])
    assert len(model.requests) == 3, "ни одной лишней попытки"
    assert layer["title"] == "Давление в скважине"
    assert verify_layer(layer, {n: "\n\n".join(u.text for u in UNITS if u.page_pdf == n) for n in PAGES}) == []
    rows = read(chapter.work / "coverage.json")["rows"]
    assert len(rows) == len(UNITS) and all(r["node_ids"] or r["reason"] for r in rows)
    quotes = [c["quote"] for c in layer["nodes"][0]["claims"]]
    assert any("driller’s “first barrier”" in q for q in quotes) and any("perme-\nability" in q for q in quotes)
    described = next(c for c in layer["nodes"][0]["claims"] if c["source_kind"] == "figure_description_model")
    assert described["by_model"] is True


def test_every_stage_asks_for_russian(chapter):
    model = Model(plan_for(UNITS))
    build_layer(chapter, model)
    for (system, _), name in zip(model.requests, ("plan", "node", "enrich"), strict=True):
        assert system.startswith((FOLDER / f"{name}.md").read_text(encoding="utf-8")) and "по-русски" in system.removeprefix((FOLDER / f"{name}.md").read_text(encoding="utf-8"))


def test_untranslated_answer_is_returned_to_the_model(chapter):
    def lazy(units):
        answer = node_answer(units)
        return {**answer, "layers": {**answer["layers"], "main": said("Pressure increases with the depth of the well.")}}

    plan = plan_for(UNITS)
    _, issues, replies = make_node(Model(plan, lazy), "Ты пишешь один узел", "", plan, 0, UNITS, "demo")
    assert len(replies) == 3 and any("перевод" in i for i in issues)
    plan["nodes"][0]["title"] = "Hydrostatic pressure of the mud"
    assert any("перевод" in i for i in plan_issues(plan, UNITS))


def test_references_do_not_stop_the_plan_but_text_does():
    plan = plan_for(UNITS)
    assert plan_issues(plan, UNITS) == []
    task = next(u.unit_id for u in UNITS if u.kind == "task")
    plan["nodes"][0]["unit_ids"].remove(task)
    plan["skipped"].append({"unit_id": task, "reason": "задача"})
    assert any(task in i for i in plan_issues(plan, UNITS))


def test_course_is_built_and_audited(chapter):
    build_layer(chapter, Model(plan_for(UNITS)))
    layer = read(chapter.work / "layer.json")
    out = build_site(chapter)
    data = json.loads((out / "data.js").read_text(encoding="utf-8").removeprefix("window.COURSE=").rstrip(";\n"))
    step = data["steps"][0]
    assert "<title>Давление в скважине</title>" in (out / "index.html").read_text(encoding="utf-8")
    assert step["tables"][0]["title"].startswith("Таблица книги, стр. 12") and step["numbers"] and len(step["book_tasks"]) == 2
    assert not is_untranslated(step["essence"])
    report = audit_layer(layer)
    assert report["prose_numbers"] == [] and report["early_terms"] == []
    assert [f for f in report["flagged"] if is_english(f["quote"]) and "column" in f["quote"]] == []


def test_tasks_take_numbers_of_the_english_book(chapter):
    build_layer(chapter, Model(plan_for(UNITS)))
    nodes = read(chapter.work / "layer.json")["nodes"]
    task = {"id": "t1", "type": "calc", "step_id": "demo.pressure", "claim_ids": ["demo.pressure#c1"], "prompt": "Глубина 8 000 футов, градиент 0,52 psi/фут. Найдите давление.", "options": [],
            "answer": 4160, "tolerance": 1, "unit": "psi", "formula": "g * d", "inputs": {"g": 0.52, "d": 8000}, "explanation": "Градиент умножают на глубину.", "kind": "data"}
    assert task_issues({"tasks": [task]}, nodes, {}) == []


# ---------- глава, которой конвейер не видел
@pytest.mark.parametrize("pages", [[[50, 60]], [[1, 1]]])
def test_chapter_without_text_stops_before_paid_requests(tmp_path, monkeypatch, pages):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    (tmp_path / "b.md").write_text("<!-- page 1 -->\n\n<!-- Page 2 -->\nText of the page.\n", encoding="utf-8")
    info = {"file": "b.md", "root": ".", "pages": pages, "prefix": "b", "domain": "own", "title": "t", "book": "b"}
    save(tmp_path / "chapters.json", {"root": ".", "pdf_root": ".", "chapters": {"b": info}})
    with pytest.raises(LibraryError, match="нет текста"):
        load_chapter("b")


def test_missing_page_is_named(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    (tmp_path / "b.md").write_text("<!-- page 1 -->\nПервая.\n<!-- Page 2 -->\nВторая страница.\n", encoding="utf-8")
    info = {"file": "b.md", "root": ".", "pages": [[1, 3]], "prefix": "b", "domain": "own", "title": "t", "book": "b"}
    save(tmp_path / "chapters.json", {"root": ".", "pdf_root": ".", "chapters": {"b": info}})
    with caplog.at_level(logging.WARNING, logger="glava"):
        assert [u.page_pdf for u in load_chapter("b").units] == [1, 2]
    assert "нет страниц 3" in caplog.text


def test_english_file_in_windows_encoding_is_not_read_as_russian():
    text = "The driller’s “first barrier” is at 150 °F – the café of the well. " * 20
    assert decoded(text.encode("cp1252"))[0] == text
    assert decoded("Пласт сложен песчаником, нефть движется к скважине.".encode("cp1251"))[0].startswith("Пласт")


# ---------- русская глава: запросы прежние
RUSSIAN = """<!-- page 5 -->
# Глава I

Обычно проницаемость пласта снижается с ростом глинистости, порог 12,5 % не меняется.

Рис. 1. Кривая ПС.

Задачи

1. Выделить коллекторы по диаграмме и оценить мощность пласта.
"""
# посчитано на коде до поддержки английского (a8c7e1c): тело запроса входит в ключ оплаченного кэша
BODIES = {"plan": "d8ef635b925f5e342f78fead5add6dfc4da54ecc24e18b543bd101bfe5ea2cee", "node": "da3a2d0614ee73833ac57bed0c929b7e8a576a80fb8d2ef16ff7fb034b7279f8",
          "enrich": "b65a09f7e9bb647096f79203a0731f7fe434b2a7e1e38c0b789f54b049accf64"}


def russian_requests(chapter):
    units = parse_units(read_pages(RUSSIAN, [(5, 5)]))
    own = [u.unit_id for u in units if u.kind != "heading"]
    node = {"slug": "perm", "title": "Проницаемость и глинистость", "short_title": "Проницаемость и глина рядом", "why_here": "Первый узел.", "difficulty": {"primary": "И", "secondary": None},
            "threshold": False, "unit_ids": own, "terms_introduced": ["проницаемость"]}
    plan = {"title": "Другое название", "parts": [{"title": "Часть", "slugs": ["perm"]}], "nodes": [node],
            "skipped": [{"unit_id": u.unit_id, "reason": "заголовок"} for u in units if u.unit_id not in own]}

    def answer(found):
        raw = node_answer([])
        claims = [{"text": "Порог 12,5 % не меняется." if u["text"].startswith("Обычно") else "Кривая ПС.", "kind": "observation", "page_pdf": 5, "unit_id": u["id"], "quote": u["text"][:200],
                   "source_kind": "text", "by_model": False, "needs_scan": False, "conditions": []} for u in found if u["kind"] != "task"]
        return {**raw, "claims": claims, "worked_examples": [], "glossary": [{"term": "проницаемость", "definition": "свойство"}],
                "book_tasks": [{"number": "1", "page_pdf": 5, "text": "Выделить коллекторы.", "figure": None}]}

    model = Model(plan, answer)
    russian = Chapter("demo_ru", "demo", "Глава", "Книга", chapter.domain, tuple(units), "demo.md")
    layer = build_layer(russian, model)
    return model.requests, layer


def test_russian_requests_are_the_same_to_the_byte(chapter, monkeypatch):
    monkeypatch.delenv("GLAVA_CONTEXT", raising=False)
    requests, layer = russian_requests(chapter)
    assert len(requests) == 3 and layer["title"] == "Глава"
    for (system, body), name in zip(requests, BODIES, strict=True):
        assert system == (FOLDER / f"{name}.md").read_text(encoding="utf-8")
        assert hashlib.sha256(body.encode()).hexdigest() == BODIES[name], name


@pytest.mark.parametrize("file", sorted(FOLDER.glob("*.md")), ids=lambda f: f.stem)
def test_russian_prompt_is_the_file_itself(file):
    assert prompt_file(file.stem) == prompt_file(file.stem, False) == file.read_text(encoding="utf-8")


def test_every_english_addition_has_its_prompt():
    for extra in (FOLDER / "english").glob("*.md"):
        assert prompt_file(extra.stem, True) == f"{prompt_file(extra.stem)}\n{extra.read_text(encoding='utf-8')}"
