from glava.stages.routing import routing_issues
from glava.stages.tasks import chapter_task_issues, number_tasks, task_issues

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


def test_calc_needs_number_tolerance_and_unit():
    assert task_issues({"tasks": [task(type="calc", options=[], answer=10, tolerance=0.5, unit="%")]}, NODES) == []
    assert task_issues({"tasks": [task(type="calc", options=[], answer=10)]}, NODES)


def test_claim_from_another_node_is_rejected():
    assert task_issues({"tasks": [task(claim_ids=["lat.b#c9"])]}, NODES)


def test_chapter_needs_fifteen_tasks_and_four_types():
    assert len(chapter_task_issues([task()])) == 2


def test_tasks_get_stable_ids():
    assert [t["id"] for t in number_tasks([task(), task()])] == ["lat.a.t1", "lat.a.t2"]
