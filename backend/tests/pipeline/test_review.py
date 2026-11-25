"""Модуль проверки чужого пакета: страницы ставит код, спорное отсеивает судья, ключ модели недоступен."""

import json

import jsonschema
import pytest
from glava.modules.llm.client import Reply, cached
from glava.modules.review.checks import quick_notes
from glava.modules.review.engine import (
    evidence_pages,
    review_package,
    settle_page,
    workspace,
)
from glava.shared.json_schemas import load_schema

PAGES = {9: "Показания ГК против глин максимальны, если нет калиевых полевых шпатов.", 10: "Сопротивление растёт с нефтенасыщением в 3 раза."}
PACKAGE = {
    "package_id": "p", "chapter": "c", "chapter_file": "c.md",
    "items": [
        {"id": "C001", "type": "claim", "text": "Показания ГК против глин всегда максимальны.", "kind": "observation", "page_pdf": 9, "quote": "Показания ГК против глин максимальны"},
        {"id": "C002", "type": "claim", "text": "Сопротивление растёт в 3 раза.", "kind": "observation", "page_pdf": 10, "quote": "растёт с нефтенасыщением в 3 раза"},
        {"id": "L01", "type": "script_line", "text": "Глина светится ярче.", "claim_ref": "C001", "video_id": "v"},
    ],
    "scenes": [], "frames": [],
}
REMARK = {"target": "C001", "category": "overgeneralization", "severity": "critical", "problem": "Потеряно условие.", "fix": "Максимальны, если нет калиевых полевых шпатов.",
          "page_pdf": 12, "quote": "если нет калиевых полевых шпатов", "confidence": 95}


class Scripted:
    """Отвечает по роли, названной в системном промпте."""

    name, model = "fake", "fake"

    def __init__(self, found, confirmed):
        self.found, self.confirmed, self.prompts = found, confirmed, []

    def ask(self, system, prompt, files=()):
        self.prompts.append(prompt)
        if "СУДЬЯ" in system:
            answer = {"verdicts": [{"target": r["target"], "confirmed": r["target"] in self.confirmed, "confidence": 90, **{k: r[k] for k in ("category", "severity", "problem", "fix", "quote", "page_pdf")}} for r in self.found]}
        else:
            answer = {"remarks": self.found}
        return Reply(json.dumps(answer, ensure_ascii=False), "fake", 1, 1, 0.0)


PROMPTS = {"find": "ПРОВЕРЯЮЩИЙ", "physics": "ФИЗИК", "judge": "СУДЬЯ"}


def test_quick_notes_point_at_numbers_and_quotes():
    bad = {**PACKAGE["items"][1], "text": "Сопротивление растёт в 7 раз.", "quote": "такой фразы в главе нет"}
    notes = quick_notes(bad, PAGES)
    assert any("7" in n for n in notes)
    assert any("цитат" in n for n in notes)
    assert quick_notes(PACKAGE["items"][1], PAGES) == []


def test_evidence_takes_neighbour_pages_and_claim_of_a_script_line():
    assert evidence_pages([PACKAGE["items"][2]], PACKAGE, PAGES) == [9, 10]


def test_page_follows_the_quote():
    assert settle_page(REMARK, PAGES, None) == 9
    assert settle_page({**REMARK, "quote": "нет такого"}, PAGES, 10) == 10


def test_confirmed_remark_gets_into_the_answer():
    answer, _ = review_package(PACKAGE, PAGES, Scripted([REMARK], {"C001"}), PROMPTS, "чек-лист")
    jsonschema.validate(answer, load_schema("review_output"))
    assert [(r["target"], r["page_pdf"]) for r in answer["remarks"]] == [("C001", 9)]


def test_rejected_and_unknown_targets_are_dropped():
    answer, _ = review_package(PACKAGE, PAGES, Scripted([REMARK, {**REMARK, "target": "X999"}], set()), PROMPTS, "")
    assert answer["remarks"] == []


def test_one_remark_per_target():
    answer, _ = review_package(PACKAGE, PAGES, Scripted([REMARK, REMARK], {"C001"}), PROMPTS, "")
    assert len(answer["remarks"]) == 1


def test_low_confidence_is_dropped():
    low = Scripted([REMARK], {"C001"})
    answer, _ = review_package(PACKAGE, PAGES, low, PROMPTS, "", min_confidence=95)
    assert answer["remarks"] == []


def test_workspace_never_contains_the_key(tmp_path):
    source = tmp_path / "in"
    (source / "frames").mkdir(parents=True)
    (source / "package.json").write_text(json.dumps(PACKAGE), encoding="utf-8")
    (source / "key.json").write_text("{}", encoding="utf-8")
    (source / "frames" / "F01.png").write_bytes(b"png")

    target = workspace(source, tmp_path, "out")

    names = {p.name for p in target.rglob("*")}
    assert "key.json" not in names
    assert {"package.json", "F01.png"} <= names


def test_cache_distinguishes_files(tmp_path):
    class Counter:
        name, model, calls = "f", "f", 0

        def ask(self, system, prompt, files=()):
            type(self).calls += 1
            return Reply("{}", "f", 1, 1, 0.0)

    one, two = tmp_path / "1.png", tmp_path / "2.png"
    one.write_bytes(b"1")
    two.write_bytes(b"2")
    provider = cached(Counter(), tmp_path / "cache")
    for files in ((one,), (two,), (one,), ()):
        provider.ask("s", "p", files)
    assert Counter.calls == 3


@pytest.mark.parametrize("missing", ["fix", "problem"])
def test_remark_without_fix_is_not_sent(missing):
    answer, _ = review_package(PACKAGE, PAGES, Scripted([{**REMARK, missing: ""}], {"C001"}), PROMPTS, "")
    assert answer["remarks"] == []


def test_swapped_condition_word_is_pointed_out():
    from glava.modules.review.checks import foreign_condition_words
    page = "При низких значениях давления и минерализации вод применяются все методы."
    assert foreign_condition_words("При умеренном давлении и низкой минерализации применяются все методы.", page) == ["умеренном"]
    assert foreign_condition_words("При низком давлении применяют все методы.", page) == []
    item = {"id": "C009", "type": "claim", "text": "Глина всегда видна.", "page_pdf": 9, "quote": "Показания ГК против глин максимальны"}
    assert any("всегда" in n for n in quick_notes(item, PAGES))


def test_frame_takes_the_page_of_the_line_spoken_at_its_time():
    pages = {9: PAGES[9], 10: PAGES[10]}
    package = {**PACKAGE, "items": [*PACKAGE["items"],
                                    {"id": "L02", "type": "script_line", "text": "Сопротивление растёт.", "claim_ref": "C002", "video_id": "v", "t_start": 5.0}],
               "frames": [{"id": "F01", "video_id": "v", "file": "frames/F01.png", "t": 7.0, "frame_class": "A", "label": "симуляция",
                           "shows": "кривая", "plaque": ""}]}
    package["items"][2] = {**package["items"][2], "t_start": 0.0}
    remark = {**REMARK, "target": "F01", "category": "frame_error", "page_pdf": 9}
    answer, _ = review_package(package, pages, Scripted([remark], {"F01"}), PROMPTS, "")
    # цитата стоит на стр. 9, но кадр в 7 с иллюстрирует фразу L02 и утверждение C002 со стр. 10
    assert [(r["target"], r["page_pdf"]) for r in answer["remarks"]] == [("F01", 10)]


def test_claim_with_sound_citation_keeps_its_own_page():
    elsewhere = {**REMARK, "target": "C002", "quote": "если нет калиевых полевых шпатов"}
    answer, _ = review_package(PACKAGE, PAGES, Scripted([elsewhere], {"C002"}), PROMPTS, "")
    # модель процитировала стр. 9, но C002 стоит на стр. 10 и его цитата там есть; чужая цитата не остаётся при чужой странице
    assert [(r["target"], r["page_pdf"], r["quote"]) for r in answer["remarks"]] == [("C002", 10, None)]


def test_claim_with_broken_citation_follows_the_quote():
    package = {**PACKAGE, "items": [{**PACKAGE["items"][1], "quote": "такой фразы в главе нет"}, *PACKAGE["items"][2:]]}
    remark = {**REMARK, "target": "C002", "quote": "если нет калиевых полевых шпатов"}
    answer, _ = review_package(package, PAGES, Scripted([remark], {"C002"}), PROMPTS, "")
    assert [(r["target"], r["page_pdf"]) for r in answer["remarks"]] == [("C002", 9)]
