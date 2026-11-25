import json

import pytest
from glava.modules.llm.client import (
    BudgetExceeded,
    Ledger,
    Reply,
    ask_json,
    cached,
    extract_json,
)


class FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def ask(self, system, prompt):
        self.calls.append(prompt)
        return Reply(self.answers.pop(0), self.model, 10, 5, 0.01)


def test_extract_json_from_a_fenced_answer():
    assert extract_json('Вот:\n```json\n{"a": [1, 2]}\n```\n') == {"a": [1, 2]}


def test_extract_json_without_fence_and_with_text_around():
    assert extract_json('итак {"a": "}"} конец') == {"a": "}"}


def test_extract_json_fails_clearly():
    with pytest.raises(ValueError, match="JSON"):
        extract_json("нет тут ничего")


def test_cached_provider_asks_once(tmp_path):
    inner = FakeProvider("ответ")
    provider = cached(inner, tmp_path)
    assert provider.ask("s", "p").text == "ответ"
    again = provider.ask("s", "p")
    assert again.text == "ответ" and again.cost_usd == 0.0
    assert len(inner.calls) == 1


def test_ledger_is_immutable_and_sums():
    one = Ledger(budget_usd=1.0)
    two = one.add("layer", Reply("x", "m", 10, 5, 0.4))
    assert one.cost_usd == 0 and two.cost_usd == pytest.approx(0.4)


def test_ledger_stops_before_spending_over_budget():
    with pytest.raises(BudgetExceeded):
        Ledger(budget_usd=0.1).add("layer", Reply("x", "m", 1, 1, 0.2)).check()


def test_ask_json_repairs_once_with_the_error_text():
    provider = FakeProvider("мусор", json.dumps({"ok": True}))
    data, replies = ask_json(provider, "s", "вопрос", validate=lambda d: [], attempts=2)
    assert data == {"ok": True} and len(replies) == 2
    assert "JSON" in provider.calls[1]


def test_ask_json_sends_validation_issues_back():
    provider = FakeProvider('{"n": 1}', '{"n": 2}')
    data, _ = ask_json(provider, "s", "q", validate=lambda d: ["n должно быть 2"] if d["n"] != 2 else [], attempts=2)
    assert data == {"n": 2}
    assert "n должно быть 2" in provider.calls[1]


def test_ask_json_returns_the_last_answer_with_remaining_issues():
    provider = FakeProvider('{"n": 1}', '{"n": 1}')
    data, replies = ask_json(provider, "s", "q", validate=lambda d: ["плохо"], attempts=2)
    assert data == {"n": 1} and len(replies) == 2
