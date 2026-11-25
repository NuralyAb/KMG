"""Блоки страницы шага из ТЗ: числа и таблицы собирает код, суть, шаги и формулы — модель под проверкой."""

import json

import pytest

from glava.llm import Reply
from glava.stages.blocks import book_tables, number_blocks
from glava.stages.enrich import apply, enrich_issues, make_enrichment
from glava.units import Unit

CLAIMS = [
    {"id": "n#c1", "text": "Оптимальная водоотдача 4—8 см³/ч.", "quote": "водоотдача (4—8 см³/ч)", "page_pdf": 90},
    {"id": "n#c2", "text": "Корка образуется против коллектора, см. рис. 58 и формулу (12).", "quote": "глинистая корка", "page_pdf": 91},
    {"id": "n#c3", "text": "Сначала строят колонку, затем выделяют коллекторы.", "quote": "строят колонку", "page_pdf": 91},
]
NODE = {"id": "n", "title": "Раствор", "short_title": "Раствор", "pages": [90, 91], "claims": CLAIMS, "unit_ids": ["p090.01"], "worked_examples": [], "book_tasks": [],
        "layers": {k: {"text": "т", "by_model": True} for k in ("topic", "main", "mechanism", "practice", "nuances")}, "now_practice": None, "inefficiency_lens": None}
LENS = {"inputs": "диаграммы", "manual_steps": "снимают отсчёты", "judgment_points": "границы пластов", "time": "в главе не указано", "typical_errors": "пропуск корки"}


def row(**over):
    return {"node_id": "n", "essence": "Раствор меняет стенку скважины. Поэтому прибор видит корку.", "short_title": "Как раствор меняет стенку", "procedure": [],
            "formulas": [], "now_practice": None, "inefficiency_lens": LENS} | over


def issues(**over):
    return enrich_issues({"nodes": [row(**over)]}, [NODE])


def test_numbers_skip_references_to_figures_and_formulas():
    assert number_blocks(NODE) == [{"text": CLAIMS[0]["text"], "page": 90, "claim_id": "n#c1"}]


TABLE = Unit("p090.01", "table", 90, "|  Порода | $k_{n_0}^*$ %  |\n| --- | --- |\n|  Рифтовые отложения (Башкирия) | 1  |\n|  Доломиты | 3  |")


def test_table_is_kept_whole_and_corrections_are_marked():
    errata = [{"page": 90, "md": "Рифтовые отложения", "scan": "Рифовые отложения", "kind": "recognition", "note": ""},
              {"page": 91, "md": "Доломиты", "scan": "Известняки", "kind": "recognition", "note": ""}]
    table = book_tables(NODE, [TABLE], errata)[0]
    assert table["header"] == ["Порода", "$k_{n_0}^*$ %"]
    assert table["rows"] == [["Рифовые отложения (Башкирия)", "1"], ["Доломиты", "3"]]
    assert table["corrections"] == [{"row": 0, "col": 0, "from": "Рифтовые отложения (Башкирия)", "to": "Рифовые отложения (Башкирия)"}]
    assert table["page"] == 90


def test_tables_of_other_nodes_are_not_shown():
    assert book_tables({**NODE, "unit_ids": []}, [TABLE], []) == []


def test_suspected_misprint_does_not_change_the_table():
    suspect = [{"page": 90, "md": "Рифтовые отложения", "scan": "Рифовые отложения", "kind": "suspect", "note": ""}]
    assert book_tables(NODE, [TABLE], suspect)[0]["corrections"] == []


def test_good_enrichment_passes():
    steps = [{"text": "Постройте колонку.", "claim_id": "n#c3"}, {"text": "Выделите коллекторы.", "claim_id": "n#c3"}]
    formula = {"tex": "B = 8", "claim_id": "n#c1", "legend": [{"symbol": "B", "meaning": "водоотдача", "unit": "см³/ч"}]}
    assert issues(procedure=steps, formulas=[formula]) == []


@pytest.mark.parametrize("over", [
    {"essence": "Одна фраза."}, {"essence": "Раз. Два. Три. Четыре."}, {"essence": "слово " * 25 + ". Вторая фраза."}, {"essence": "Порог 77 %. Это мало."},
    {"short_title": "Раствор"}, {"short_title": "Очень длинный заголовок шага из целых восьми слов"}, {"procedure": [{"text": "Один шаг.", "claim_id": "n#c3"}]},
    {"procedure": [{"text": "Раз.", "claim_id": "n#c9"}, {"text": "Два.", "claim_id": "n#c3"}]}, {"formulas": [{"tex": "x = 99", "claim_id": "n#c1", "legend": [{"symbol": "x", "meaning": "и", "unit": ""}]}]},
    {"formulas": [{"tex": "x = {y", "claim_id": "n#c1", "legend": [{"symbol": "x", "meaning": "и", "unit": ""}]}]}, {"formulas": [{"tex": "x", "claim_id": "n#c1", "legend": []}]},
    {"now_practice": "Теперь 77 приборов."}, {"inefficiency_lens": {"inputs": "только одно поле"}}, {"node_id": "чужой"},
])
def test_wrong_enrichment_is_reported(over):
    assert issues(**over)


def test_every_node_must_be_enriched():
    assert enrich_issues({"nodes": []}, [NODE])


def test_apply_keeps_the_author_fields_and_marks_the_model():
    done = apply(NODE, row(now_practice="Теперь пишут цифровой записью."), [TABLE], [])
    assert done["layers"]["main"] == {"text": row()["essence"], "by_model": True}
    assert done["short_title"] == "Как раствор меняет стенку"
    assert done["now_practice"] == {"text": "Теперь пишут цифровой записью.", "by_model": True}
    assert done["inefficiency_lens"]["by_model"] is True
    assert done["numbers"] and done["tables"]
    assert done["claims"] == CLAIMS
    assert NODE["short_title"] == "Раствор"


def test_existing_lens_is_not_replaced_by_nothing():
    node = {**NODE, "inefficiency_lens": {**LENS, "by_model": False}}
    assert apply(node, row(inefficiency_lens=None), [], [])["inefficiency_lens"] == node["inefficiency_lens"]


def test_failed_answer_leaves_the_node_as_it_was():
    class Bad:
        name, model = "f", "f"

        def ask(self, system, prompt, files=()):
            return Reply(json.dumps({"nodes": [row(essence="Одна фраза.")]}, ensure_ascii=False), "f", 1, 1, 0.0)

    rows, _ = make_enrichment(Bad(), "s", [NODE], "")
    assert rows == {}
    assert apply(NODE, None, [], [])["layers"] == NODE["layers"]
