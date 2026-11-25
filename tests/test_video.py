"""Ролик: таймлайн, субтитры, паспорт и проверки сценария — без сети и без рендера."""

import json
from pathlib import Path

import jsonschema
import pytest

from glava.stages.layer import load_schema
from glava.video.check import script_errors, speech_rate, word_error_rate
from glava.video.passport import build_passport
from glava.video.speech import Speech, Word, dictionaries, spoken
from glava.video.timeline import place, srt, state_at

NODE = {"id": "lat.mud", "title": "Раствор", "claims": [{"id": "lat.mud#c1", "text": "Против коллектора корка сужает ствол.", "quote": "сужение диаметра", "page_pdf": 96}]}


def beat(say, **over):
    return {"say": say, "claim_id": "lat.mud#c1", "on_screen": "Корка сужает ствол", "label": "симуляция", "frame_class": "B", "action": {}, "is_analogy": False,
            "pause_after": 0.0, "role": "step"} | over


SPEC = {
    "video_id": "lat_v1", "chapter": "latyshova", "node_id": "lat.mud", "format": "short", "template": "well_tool_curve", "params": {}, "objects": ["ствол"],
    "invariants": ["глубина вниз"], "assumptions": ["без масштаба"], "exaggerations": ["ствол шире в 20 раз"], "plaque": ["не в масштабе"],
    "prediction_question": "Где ствол уже?", "transfer_question": "А если бурить на воде?", "data_it_bridge": "Кавернограмма — столбец данных.", "terms_to_check": ["корка"],
    "beats": [beat("Почему скважина местами уже долота?", role="hook", on_screen="Уже долота?"),
              beat("Угадайте, где ствол сузится.", role="prediction", pause_after=1.2, action={"tool": 2.0}),
              beat("Против коллектора: там растёт глинистая корка.", role="answer", action={"tool": 10.0, "cake": 1.0}),
              beat("А если бурить на воде?", role="transfer")],
}


def speeches():
    return [Speech(Path("x.mp3"), 2.0, (Word(0.0, 0.5, "слово"), Word(0.6, 0.9, "второе"))) for _ in SPEC["beats"]]


def test_beats_follow_each_other_with_pauses():
    placed, total = place(SPEC["beats"], speeches())
    assert placed[0].start == pytest.approx(0.2)
    assert all(b.start >= a.end for a, b in zip(placed, placed[1:], strict=False))
    assert placed[2].start - placed[1].end >= 1.2
    assert total >= placed[-1].end + 2


def test_state_moves_smoothly_and_holds():
    placed, total = place(SPEC["beats"], speeches())
    start = {"tool": 0.0, "cake": 0.0}
    assert state_at(0.0, placed, start) == start
    middle = state_at((placed[1].start + placed[1].end) / 2, placed, start)
    assert 0 < middle["tool"] < 2
    assert state_at(total, placed, start) == {"tool": 10.0, "cake": 1.0}


def test_subtitles_carry_the_full_text():
    placed, _ = place(SPEC["beats"], speeches())
    text = srt(placed)
    assert text.startswith("1\n00:00:00,200 --> ")
    assert "глинистая корка" in text


def test_script_rules():
    assert script_errors(SPEC, NODE) == []
    bad = [
        {"beats": [beat("слово " * 20)] + SPEC["beats"][1:]},
        {"beats": [beat("Корка шириной 77 сантиметров.")] + SPEC["beats"][1:]},
        {"beats": [beat("Так.", claim_id="lat.mud#c9")] + SPEC["beats"][1:]},
        {"beats": [beat("Так.", on_screen="очень длинная подпись из девяти разных слов на экране")] + SPEC["beats"][1:]},
        {"beats": [beat("Так.", on_screen="ρп растёт")] + SPEC["beats"][1:]},
        {"beats": SPEC["beats"][1:]}, {"beats": SPEC["beats"][:-1]},
        {"beats": [{**b, "pause_after": 0} for b in SPEC["beats"]]}, {"exaggerations": []},
        {"beats": [beat("Так.", claim_id=None)] + SPEC["beats"][1:]},
    ]
    for change in bad:
        assert script_errors({**SPEC, **change}, NODE), change


def test_word_errors_ignore_case_and_yo():
    assert word_error_rate("Растёт глинистая корка", "растет глинистая корка.") == 0
    assert word_error_rate("один два три четыре", "один два пять четыре") == pytest.approx(0.25)


def test_speech_rate_counts_words_per_minute():
    placed, _ = place(SPEC["beats"], speeches())
    assert speech_rate(placed) == pytest.approx(len(" ".join(b["say"] for b in SPEC["beats"]).split()) / 8 * 60)


def test_abbreviations_are_spelled_for_the_voice():
    table = {"ГИС": "гэ и эс", "Kп": "ка пэ"}
    assert spoken("По ГИС видно. ГИСы нет.", table, {}) == "По гэ и эс видно. ГИСы нет."
    assert spoken("дебит растёт", {}, {"дебит": "де́бит"}) == "де́бит растёт"
    assert spoken("Дебит растёт", {}, {"дебит": "де́бит"}) == "Де́бит растёт"


def test_dictionaries_are_read_from_the_domain_pack():
    text = (Path(__file__).resolve().parents[1] / "domain/geology/pronunciation.md").read_text(encoding="utf-8")
    short, stress = dictionaries(text)
    assert short["ГИС"] == "гэ и эс"
    assert short["Kв"] == "ка вэ"
    assert stress["дебит"] == "де́бит"


def test_passport_matches_the_schema():
    placed, _ = place(SPEC["beats"], speeches())
    checklist = [{"id": "pc.depth_down", "item": "Глубина вниз"}]
    passport = build_passport(SPEC, NODE, placed, "scene.json", checklist, {"pc.depth_down": ("да", "ось вниз")}, {"wer": 0.0})
    jsonschema.validate(passport, load_schema("passport"))
    assert passport["sources"][0]["page_or_dataset"] == "стр. 96"
    assert json.dumps(passport, ensure_ascii=False)
