"""Иллюстрации: спецификация от модели, рисунок и паспортные поля — от кода."""

import json
from pathlib import Path

import jsonschema
import pytest

from glava.llm import Reply
from glava.scenes import load_templates
from glava.stages.illustrations import illustration_issues, make_illustrations, records
from glava.stages.layer import load_schema

DOMAIN = Path(__file__).resolve().parents[1] / "domain" / "geology"
STYLE = json.loads((DOMAIN / "styleguide.json").read_text(encoding="utf-8"))
TEMPLATES = load_templates(DOMAIN / "templates")
NODES = [{"id": "lat.a", "short_title": "Глина", "layers": {"main": {"text": "Глинистость от 5 до 20 %."}}, "pages": [90],
          "claims": [{"id": "lat.a#c1", "text": "Глинистость от 5 до 20 %.", "quote": "от 5 до 20 %", "page_pdf": 90}]}]


def scene(**over):
    return {"node_id": "lat.a", "template": "bars", "caption": "Диапазон глинистости", "alt": "Полоса от 5 до 20 процентов", "claim_ids": ["lat.a#c1"],
            "data": {"unit": "%", "items": [{"name": "глина", "from": 5, "to": 20}, {"name": "граница", "value": 20}]}} | over


def issues(item):
    return illustration_issues({"illustrations": [item]}, NODES, TEMPLATES, STYLE)


def test_valid_scene_has_no_issues():
    assert issues(scene()) == []


@pytest.mark.parametrize("bad", [
    {"template": "hologram"}, {"claim_ids": ["lat.b#c1"]}, {"claim_ids": []}, {"caption": "Предел 77 %"}, {"data": {"unit": "%"}},
    {"data": {"unit": "%", "items": [{"name": "глина", "from": 5, "to": 33}, {"name": "б", "value": 20}]}},
])
def test_wrong_scene_is_reported(bad):
    assert issues(scene(**bad))


def test_every_node_needs_a_scene():
    assert illustration_issues({"illustrations": []}, NODES, TEMPLATES, STYLE)


def test_records_match_the_schema_and_files_are_written(tmp_path):
    found = records([scene()], NODES, TEMPLATES, STYLE, tmp_path)

    jsonschema.validate({"chapter": "x", "illustrations": found}, load_schema("illustration"))
    assert found[0]["label"] == "схема"
    assert found[0]["origin"] == "code_from_data"
    assert (tmp_path / Path(found[0]["file"]).name).read_text(encoding="utf-8").startswith("<svg")


class Fake:
    name, model = "fake", "fake"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def ask(self, system, prompt):
        self.prompts.append(prompt)
        return Reply(json.dumps(self.answers.pop(0), ensure_ascii=False), "fake", 1, 1, 0.0)


def test_bad_scene_is_never_drawn():
    fake = Fake(*[{"illustrations": [scene(template="hologram")]}] * 3)
    scenes, replies = make_illustrations(fake, "s", NODES, TEMPLATES, STYLE)
    assert scenes == []
    assert len(replies) == 3


def test_prompt_lists_templates_and_claims():
    fake = Fake({"illustrations": [scene()]})
    scenes, _ = make_illustrations(fake, "s", NODES, TEMPLATES, STYLE)
    assert len(scenes) == 1
    assert "borehole" in fake.prompts[0]
    assert "lat.a#c1" in fake.prompts[0]
