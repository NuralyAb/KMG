import pytest
from glava.modules.format_routing.planner import routing_issues
from glava.modules.tasks.generator import chapter_task_issues, number_tasks, task_issues

NODES = [{"id": "lat.a", "claims": [{"id": "lat.a#c1", "text": "Порог 10 %."}], "layers": {}}]


def route(**over):
    return {"node_id": "lat.a", "format": "текст", "secondary_format": None, "hook_short": False, "template": None, "why": "Пр",
            "video_scores": dict.fromkeys(("time", "invisible", "scale", "counterintuitive", "cause_effect"), 0)} | over


def task(**over):
    return {"id": "t1", "type": "single", "step_id": "lat.a", "claim_ids": ["lat.a#c1"], "prompt": "Какой порог?", "answer": "a",
            "options": [{"id": "a", "text": "10 %"}, {"id": "b", "text": "другой"}], "explanation": "Так сказано.", "kind": "recall"} | over


def test_every_node_needs_exactly_one_route():
    assert routing_issues({"routes": [route()]}, NODES) == []
    assert routing_issues({"routes": []}, NODES)


def test_unknown_format_is_rejected():
    assert routing_issues({"routes": [route(format="мультфильм")]}, NODES)


def test_valid_task_has_no_issues():
    assert task_issues({"tasks": [task()]}, NODES) == []


def test_answer_must_be_one_of_the_options():
    assert any("t1" in i for i in task_issues({"tasks": [task(answer="z")]}, NODES))


def test_multiple_needs_two_answers():
    assert task_issues({"tasks": [task(type="multiple", answer=["a"])]}, NODES)


def test_order_answer_lists_every_option_once():
    assert task_issues({"tasks": [task(type="order", answer=["a"])]}, NODES)
    assert task_issues({"tasks": [task(type="order", answer=["b", "a"])]}, NODES) == []


def test_gap_count_matches_the_answers():
    assert task_issues({"tasks": [task(type="gap", prompt="Порог {{1}} %", options=[], answer=["10"])]}, NODES) == []
    assert task_issues({"tasks": [task(type="gap", prompt="Порог {{1}} и {{2}}", options=[], answer=["10"])]}, NODES)


SUM_NODES = [{"id": "lat.a", "claims": [{"id": "lat.a#c1", "text": "Толщина 24 м, прослои 3,5 м и 1 000 Па.", "quote": ""}], "layers": {}}]


def calc(**over):
    return task(**{"type": "calc", "options": [], "prompt": "Толщина 24 м, прослои 3,5 м. Сколько осталось?", "answer": 20.5, "tolerance": 0.1, "unit": "м",
                   "formula": "h - s", "inputs": {"h": 24, "s": 3.5}} | over)


def test_calc_is_counted_by_code():
    assert task_issues({"tasks": [calc()]}, SUM_NODES, {}) == []
    assert any("получается" in i for i in task_issues({"tasks": [calc(answer=21.5)]}, SUM_NODES, {}))


def test_grouped_digits_are_one_number():
    ok = calc(prompt="Давление 1 000 Па разделили на 24.", answer=1000 / 24, formula="p / h", inputs={"p": 1000, "h": 24})
    assert task_issues({"tasks": [ok]}, SUM_NODES, {}) == []


@pytest.mark.parametrize(("prompt", "formula", "inputs", "answer"), [
    ("Проницаемость 2,5·10⁻³ делят на 24.", "k / h", {"k": 0.0025, "h": 24}, 0.0025 / 24), ("Сдвиг −15 м прибавили к 24 м.", "a + b", {"a": -15, "b": 24}, 9),
    ("Порог 10⁻³ умножили на 24.", "k * h", {"k": 0.001, "h": 24}, 0.024), ("Интервал 3,5–24 м.", "b - a", {"a": 3.5, "b": 24}, 20.5),
    ("Доля 12 % от 24 м.", "p * h", {"p": 0.12, "h": 24}, 2.88), ("Берут 1/2 от 24.", "q * h", {"q": 0.5, "h": 24}, 12),
    ("Толщина 24 м, прослои 3,5 м. Ответ округлите до 0,1.", "ρ₁ − s", {"ρ₁": 24, "s": 3.5}, 20.5),
])
def test_ordinary_ways_to_write_a_number(prompt, formula, inputs, answer):
    nodes = [{"id": "lat.a", "claims": [{"id": "lat.a#c1", "text": "24 3,5 2,5·10⁻³ 15 12 % 1/2", "quote": ""}], "layers": {}}]
    made = calc(prompt=prompt, formula=formula, inputs=inputs, answer=answer, tolerance=0)
    assert task_issues({"tasks": [made]}, nodes, {}) == []


def test_percent_answer_needs_a_hundred():
    made = calc(prompt="Из 24 м прослои 3,5 м.", formula="s / h * 100", unit="%", answer=3.5 / 24 * 100)
    assert task_issues({"tasks": [made]}, SUM_NODES, {}) == []


def test_invented_gap_answer_and_explanation_are_refused():
    gap = task(type="gap", prompt="Порог {{1}} %", options=[])
    assert task_issues({"tasks": [gap | {"answer": ["99"]}]}, NODES, {})
    assert task_issues({"tasks": [task(explanation="Потому что 77.")]}, NODES, {})


def test_broken_calc_is_refused():
    for over in ({"formula": None}, {"inputs": {}}, {"inputs": {"h": True, "s": 3.5}}, {"formula": "__import__('os')"}, {"formula": "h / 0"},
                 {"tolerance": float("inf")}, {"tolerance": -1}, {"tolerance": 1000, "answer": 5}, {"formula": "20.5"}, {"formula": "h * 1.7", "inputs": {"h": 24}, "answer": 40.8},
                 {"answer": 10**400}, {"inputs": {"h": -24, "s": 3.5}, "answer": -27.5}, {"formula": "h * 100", "inputs": {"h": 24}, "answer": 2400},
                 {"unit": "%", "formula": "h / s", "answer": 24 / 3.5}, {"prompt": "Давление 2·10^9999 и 24 и 3,5"[:24]}, {"prompt": "9" * 400 + "/3"}, {"inputs": {"h": 0.24, "s": 3.5}}, {"unit": "%", "formula": "s / h", "answer": 3.5 / 24, "tolerance": 0}, {"inputs": {"h": 24, "s": 3.5, "x": 77}}):
        assert task_issues({"tasks": [calc(**over)]}, SUM_NODES, {}), over


def test_invented_numbers_are_refused_unless_allowed():
    invented = calc(prompt="Толщина 30 м, прослои 4 м. Сколько осталось?", answer=26, inputs={"h": 30, "s": 4})
    assert any("чисел нет в узле" in i for i in task_issues({"tasks": [invented]}, SUM_NODES, {}))
    assert task_issues({"tasks": [invented]}, SUM_NODES, {"GLAVA_FREE_NUMBERS": "1"}) == []


def test_wrong_options_may_hold_any_numbers_but_the_right_one_may_not():
    options = [{"id": "a", "text": "10 %"}, {"id": "b", "text": "77 %"}]
    assert task_issues({"tasks": [task(options=options)]}, NODES, {}) == []
    assert task_issues({"tasks": [task(options=options, answer="b")]}, NODES, {})


def test_calc_needs_number_tolerance_and_unit():
    assert task_issues({"tasks": [task(type="calc", options=[], answer=10)]}, NODES)


def test_claim_from_another_node_is_rejected():
    assert task_issues({"tasks": [task(claim_ids=["lat.b#c9"])]}, NODES)


def test_chapter_needs_fifteen_tasks_and_four_types():
    assert len(chapter_task_issues([task()])) == 2


def test_tasks_get_stable_ids():
    assert [t["id"] for t in number_tasks([task(), task()])] == ["lat.a.t1", "lat.a.t2"]
