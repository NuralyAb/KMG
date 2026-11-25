"""Спецификация ролика: модель пишет сценарий, код проверяет форму, длину, физику и голос."""

import json
from types import SimpleNamespace

import pytest
from test_video import NODE, SPEC

from glava.llm import Reply
from glava.video.spec import make_spec, spec_issues

CHECKLIST = [{"id": "pc.depth_down", "group": "Кадры", "item": "Глубина вниз"}]
PHYSICS = {"pc.depth_down": {"answer": "да", "note": "ось глубины подписана"}}
TEMPLATE = SimpleNamespace(SUMMARY="well_tool_curve — сцена", check=lambda params, beats: ["слои не по порядку"] if params.get("bad") else [])
FULL = {**SPEC, "physics": PHYSICS, "beats": SPEC["beats"][:1] + [{**SPEC["beats"][2], "role": "step", "say": "Против коллектора растёт глинистая корка, и прибор видит меньший диаметр."}] * 9 + SPEC["beats"][1:]}


def issues(**over):
    return spec_issues({**FULL, **over}, NODE, TEMPLATE, CHECKLIST, "short")


def test_full_spec_passes():
    assert issues() == []


@pytest.mark.parametrize("over", [
    {"params": {"bad": True}}, {"beats": SPEC["beats"]}, {"physics": {}}, {"physics": {"pc.depth_down": {"answer": "нет", "note": ""}}},
    {"title": None, "beats": [{**b, "role": "чудо"} for b in FULL["beats"]]}, {"beats": [{k: v for k, v in b.items() if k != "say"} for b in FULL["beats"]]},
    {"beats": [{**b, "action": {"tool": "вниз"}} for b in FULL["beats"]]},
])
def test_wrong_spec_is_reported(over):
    assert issues(**over)


def test_model_gets_the_claims_and_the_code_sets_service_fields():
    class Fake:
        name, model, prompts = "f", "f", []

        def ask(self, system, prompt, files=()):
            self.prompts.append(prompt)
            return Reply(json.dumps({k: v for k, v in FULL.items() if k not in ("video_id", "format", "node_id", "chapter", "template")}, ensure_ascii=False), "f", 1, 1, 0.0)

    fake = Fake()
    spec, _ = make_spec(fake, "s", NODE, TEMPLATE, "well_tool_curve", CHECKLIST, "short", "lat_v1", "latyshova")
    assert spec["video_id"] == "lat_v1"
    assert spec["format"] == "short"
    assert "lat.mud#c1" in fake.prompts[0]


def test_spec_with_issues_is_refused():
    class Bad:
        name, model = "f", "f"

        def ask(self, system, prompt, files=()):
            return Reply("{}", "f", 1, 1, 0.0)

    with pytest.raises(ValueError):
        make_spec(Bad(), "s", NODE, TEMPLATE, "well_tool_curve", CHECKLIST, "short", "v", "c")


def test_audio_problems_are_named():
    from glava.video.produce import audio_problems

    assert audio_problems({"wer": 0.05, "words_per_minute": 130, "lufs": -16.1}) == []
    assert len(audio_problems({"wer": 0.3, "words_per_minute": 180, "lufs": -23})) == 3
