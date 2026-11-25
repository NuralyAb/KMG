"""Живой факт: что задела правка и как число расходится по тексту."""

from typing import Any

import pytest
from glava.modules.impact.diff import changes, snapshot, what_if
from glava.modules.impact.reach import reach
from glava.modules.impact.spread import leftovers, patch_number, spread

TEXT = "Критическое водонасыщение коллектора kв.кр = 56 %, при нём Pн = 3."
QUOTE = "критическое водонасыщение коллектора kв.кр = 56 %, при нём Pн = 3"


def claim(text: str = TEXT) -> dict[str, Any]:
    return {"id": "a.n#c1", "text": text, "quote": QUOTE, "page_pdf": 10, "kind": "observation"}


def layer(text: str = TEXT) -> dict[str, Any]:
    return {"chapter": "a", "nodes": [{
        "id": "a.n", "order": 1, "short_title": "Узел", "claims": [claim(text)], "numbers": [{"text": "Порог 56 %", "claim_id": "a.n#c1", "page": 10}],
        "layers": {"main": {"text": "Берём kв.кр = 56 %. Толщина пласта 56 м."}, "practice": {"text": "Водонасыщение коллектора сравнивают с 56 %."}},
        "worked_examples": [{"condition": "Найти kв.кр", "steps": ["kв.кр = 56 %"], "result": "56", "page_pdf": 10}]}]}


def changed(text: str = TEXT.replace("56", "58")) -> Any:
    found, _ = changes(snapshot(layer()), layer(text))
    return found


def test_untouched_layer_has_no_changes() -> None:
    assert changes(snapshot(layer()), layer()) == ([], {})


def test_changed_number_is_a_serious_conflict_with_the_quote() -> None:
    (found,) = changed()
    assert (found.kind, found.old_numbers, found.new_numbers) == ("changed", ("56",), ("58",))
    assert found.is_serious and "number" in found.conflicts


def test_old_conflicts_are_not_blamed_on_the_new_edit() -> None:
    wrong = claim(TEXT.replace("56", "57"))
    assert "number" not in what_if(wrong, "a.n", wrong["text"] + " Иначе нельзя.").conflicts


def test_changed_field_of_a_node_is_seen() -> None:
    fresh = layer()
    fresh["nodes"][0]["short_title"] = "Другое имя"
    assert changes(snapshot(layer()), fresh) == ([], {"a.n": ["short_title"]})


def test_added_and_removed_claims() -> None:
    empty = {"chapter": "a", "nodes": [{"id": "a.n", "order": 1, "short_title": "Узел", "claims": []}]}
    assert [c.kind for c in changes(snapshot(layer()), empty)[0]] == ["removed"]
    assert [c.kind for c in changes(snapshot(empty), layer())[0]] == ["added"]


def test_number_spreads_only_where_it_is_about_the_same_thing() -> None:
    fresh, _, log, broken = spread(layer(TEXT.replace("56", "58")), [], changed())
    node = fresh["nodes"][0]
    assert node["layers"]["main"]["text"] == "Берём kв.кр = 58 %. Толщина пласта 56 м."
    assert node["layers"]["practice"]["text"] == "Водонасыщение коллектора сравнивают с 58 %."
    assert node["numbers"][0]["text"] == "Порог 58 %"
    assert len(log) == 3 and broken == []


def test_words_of_the_author_stay_and_are_reported() -> None:
    fresh, *_ = spread(layer(TEXT.replace("56", "58")), [], changed())
    node = fresh["nodes"][0]
    assert node["worked_examples"] == layer()["nodes"][0]["worked_examples"]
    assert {row["where"].split("[")[0] for row in leftovers(node, changed()[0])} == {"a.n.layers.main.text", "a.n.worked_examples"}


def test_source_layer_is_not_mutated() -> None:
    source = layer(TEXT.replace("56", "58"))
    spread(source, [], changed())
    assert source == layer(TEXT.replace("56", "58"))


def test_two_numbers_at_once_are_not_guessed() -> None:
    found = changed("Критическое водонасыщение коллектора kв.кр = 58 %, при нём Pн = 4.")
    fresh, _, log, _ = spread(layer(), [], found)
    assert log == [] and fresh["nodes"][0]["layers"] == layer()["nodes"][0]["layers"]


@pytest.mark.parametrize(("text", "expected"), [("kв.кр = 56,5 %", "kв.кр = 56,5 %"), ("kв.кр = 156", "kв.кр = 156"), ("kв.кр = 56.", "kв.кр = 58."), ("kв.кр = 56, иначе", "kв.кр = 58, иначе")])
def test_neighbouring_numbers_are_safe(text: str, expected: str) -> None:
    assert patch_number(text, changed()[0]) == expected


def task(kind: str, answer: Any, texts: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"id": f"t.{kind}", "type": kind, "step_id": "a.n", "claim_ids": ["a.n#c1"], "prompt": "Чему равно kв.кр = 56 %?", "answer": answer, "explanation": "56 %",
            "options": [{"id": str(i), "text": t} for i, t in enumerate(texts)]}


def test_tasks_follow_the_fact_or_are_hidden() -> None:
    tasks = [task("single", "0", ("56 %", "80 %")), task("gap", ["56"]), task("calc", 56), {**task("single", "0", ("56 %", "58 %")), "id": "t.same"}]
    _, fresh, _, broken = spread(layer(), tasks, changed())
    assert fresh[0]["options"][0]["text"] == "58 %" and fresh[0]["prompt"] == "Чему равно kв.кр = 58 %?"
    assert fresh[1]["answer"] == ["58"]
    assert broken == ["t.calc", "t.same"], "расчёт и совпавшие варианты код сам не чинит"


def test_task_of_another_claim_is_left_alone() -> None:
    other = {**task("gap", ["56"]), "claim_ids": ["a.n#c9"]}
    assert spread(layer(), [other], changed())[1:] == ([other], *spread(layer(), [other], changed())[2:])


def test_reach_tells_old_number_from_mere_dependency() -> None:
    pictures = [{"id": "p1", "step_id": "a.n", "caption": "кривая", "claim_ids": ["a.n#c1"]}, {"id": "p2", "step_id": "a.n", "caption": "иное", "claim_ids": ["a.n#c1"]}]
    passports = {"v": {"node_id": "a.n", "sources": [{"claim_id": "a.n#c1"}], "script": [{"claim_id": "a.n#c1", "text": "пятьдесят шесть процентов"}]}}
    got = reach(layer(), changed(), {}, [task("calc", 56)], pictures, {"p1": "ось 56 %"}, {"a.n": [{"scene": "s", "claims": ["a.n#c1"]}]}, passports)
    assert [s["id"] for s in got["steps"]] == ["a.n"]
    assert [p["is_certain"] for p in got["pictures"]] == [True, False]
    assert got["tasks"][0]["is_certain"] and [v["id"] for v in got["videos"]] == ["v"] and got["simulations"][0]["id"] == "s"
