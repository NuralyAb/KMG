import json
import re
from pathlib import Path

import pytest
from glava.modules.course.build import (
    build_course,
    course_data,
    paragraphs,
    reading_minutes,
    source_pages,
)

CLAIMS = [{"id": "lat.a#c1", "text": "Плотность раствора определяет давление в скважине.", "page_pdf": 90, "kind": "observation", "quote": "Плотность раствора", "source_kind": "text", "by_model": False},
          {"id": "lat.a#c2", "text": "Минерализация связана с сопротивлением фильтрата.", "page_pdf": 91, "kind": "inference", "quote": "Минерализация С", "source_kind": "text", "by_model": False}]


def field(text):
    return {"text": text, "by_model": True}


def node(node_id="lat.a", order=1):
    return {"id": node_id, "order": order, "title": "Раствор", "short_title": "Раствор и измерения", "why_here": field("первый"), "pages": [90, 91],
            "difficulty": {"primary": "И", "secondary": None}, "threshold": False, "claims": CLAIMS, "links": [], "misconception": None,
            "layers": {"topic": field("т"), "main": field("Суть одна. Суть два."), "mechanism": field("Плотность раствора задаёт давление в скважине."),
                       "practice": field("п"), "nuances": field("н"), "deeper": []},
            "data_meaning": {"from_chapter": field("д"), "breaks": field("л"), "hypotheses": []}, "it_analogy": {"text": "а", "breaks_where": "г", "by_model": True},
            "now_practice": None, "inefficiency_lens": None, "decision_on_data": None, "worked_examples": [], "book_tasks": [],
            "terms_introduced": ["репрессия"], "terms_used": [], "glossary": [{"term": "репрессия", "definition": "превышение давления"}], "needs_scan": []}


LAYER = {"chapter": "lat", "title": "Глава", "book": "Книга", "source": "x.md", "generated_by": "fake", "parts": [{"title": "Часть", "nodes": ["lat.a"]}], "nodes": [node()]}
TASKS = [{"id": "lat.a.t1", "type": "single", "step_id": "lat.a", "claim_ids": ["lat.a#c1"], "prompt": "?", "options": [], "answer": "a", "explanation": "э", "kind": "recall"}]


def read_data(out):
    return json.loads((out / "data.js").read_text(encoding="utf-8").removeprefix("window.COURSE=").rstrip(";\n"))


def test_paragraphs_keep_every_sentence():
    text = "Раз. Два. Три. Четыре. Пять."
    assert " ".join(paragraphs(text)) == text and len(paragraphs(text)) > 1


def test_source_pages_come_from_the_closest_claims():
    assert source_pages("Плотность раствора задаёт давление в скважине.", CLAIMS, [90, 91]) == [90]


def test_source_pages_fall_back_to_the_node_pages():
    assert source_pages("Совсем другое.", CLAIMS, [90, 91]) == [90, 91]


def test_every_paragraph_has_a_page():
    step = course_data(LAYER, {"routes": []}, TASKS, [])["steps"][0]
    assert all(p["pages"] for block in step["how"] for p in block["paragraphs"])


def test_tasks_are_attached_to_their_step():
    assert course_data(LAYER, {"routes": []}, TASKS, [])["steps"][0]["tasks"][0]["id"] == "lat.a.t1"


def test_reading_time_is_at_least_two_minutes():
    assert reading_minutes(node()) >= 2


def test_course_opens_without_a_server(tmp_path):
    out = build_course(LAYER, {"routes": []}, TASKS, [], tmp_path)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html and 'lang="ru"' in html
    payload = (out / "data.js").read_text(encoding="utf-8")
    assert json.loads(payload.removeprefix("window.COURSE=").rstrip(";\n"))["title"] == "Глава"
    assert (out / "assets" / "course.js").exists()


def test_closing_script_tag_in_text_cannot_break_the_page(tmp_path):
    nasty = {**LAYER, "title": "</script><b>"}
    build_course(nasty, {"routes": []}, TASKS, [], tmp_path)
    assert "</script>" not in (tmp_path / "data.js").read_text(encoding="utf-8")


EXTRAS = {"lat.a": {
    "procedure": [{"text": "Сначала замеряют.", "pages": [90]}],
    "numbers": [{"text": "kп меньше 5 %", "page": 90, "claim_id": "lat.a#c1"}],
    "formulas": [{"tex": "a=b", "page": 91, "legend": [{"symbol": "a", "meaning": "что-то", "unit": "м"}], "errata": None}],
    "tables": [{"title": "Табл. 1", "page": 91, "header": ["x"], "rows": [["1"]], "corrections": [{"row": 0, "col": 0, "from": "7", "to": "1"}]}],
    "interactive": {"kind": "slider", "params": {}},
}}


def steps(extras=None):
    return course_data(LAYER, {"routes": [{"node_id": "lat.a", "format": "карточки", "why": "перечень"}]}, TASKS, [], extras)["steps"]


def test_extra_blocks_reach_the_step():
    step = steps(EXTRAS)[0]
    assert {k: step[k] for k in EXTRAS["lat.a"]} == EXTRAS["lat.a"] and step["videos"] == []


def test_enriched_node_brings_its_own_blocks():
    layer = {**LAYER, "nodes": [{**node(), **{k: EXTRAS["lat.a"][k] for k in ("procedure", "numbers", "formulas", "tables")}}]}
    step = course_data(layer, {"routes": []}, TASKS, [])["steps"][0]
    assert all(step[k] == EXTRAS["lat.a"][k] for k in ("procedure", "numbers", "formulas", "tables"))


def test_extras_win_over_the_node():
    layer = {**LAYER, "nodes": [{**node(), "numbers": [{"text": "из слоя", "page": 90}]}]}
    step = course_data(layer, {"routes": []}, TASKS, [], {"lat.a": {"numbers": EXTRAS["lat.a"]["numbers"]}})["steps"][0]
    assert step["numbers"] == EXTRAS["lat.a"]["numbers"]


def test_steps_without_extras_get_empty_blocks():
    step = steps()[0]
    assert [step[k] for k in ("procedure", "numbers", "formulas", "tables", "videos", "interactive")] == [[], [], [], [], [], None]


def test_extras_of_an_unknown_step_are_an_error():
    with pytest.raises(ValueError, match="lat.zzz"):
        steps({"lat.zzz": {}})


def test_unknown_extra_block_is_an_error():
    with pytest.raises(ValueError, match="procedures"):
        steps({"lat.a": {"procedures": []}})


def test_route_reason_reaches_the_step():
    assert steps()[0]["format"] == "карточки" and steps()[0]["format_why"] == "перечень"


def test_video_files_are_copied_and_subtitles_work_without_a_server(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "v.mp4").write_bytes(b"mp4")
    (tmp_path / "in" / "v.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nПривет\n", encoding="utf-8")
    video = {"src": str(tmp_path / "in" / "v.mp4"), "subtitles": str(tmp_path / "in" / "v.vtt"), "title": "Ролик", "format": "16:9", "label": "симуляция"}
    out = build_course(LAYER, {"routes": []}, TASKS, [], tmp_path / "out", extras={"lat.a": {"videos": [video]}})
    built = read_data(out)["steps"][0]["videos"][0]
    assert built["src"] == "videos/v.mp4" and (out / "videos" / "v.mp4").read_bytes() == b"mp4"
    assert "Привет" in built["vtt"] and built["title"] == "Ролик"


def test_video_already_in_the_course_folder_keeps_its_path(tmp_path):
    (tmp_path / "videos").mkdir()
    (tmp_path / "videos" / "v.vtt").write_text("WEBVTT\n", encoding="utf-8")
    video = {"src": "videos/v.mp4", "subtitles": "videos/v.vtt", "title": "Ролик", "format": "9:16", "label": "схема"}
    built = read_data(build_course(LAYER, {"routes": []}, TASKS, [], tmp_path, extras={"lat.a": {"videos": [video]}}))["steps"][0]["videos"][0]
    assert built["src"] == "videos/v.mp4" and built["vtt"] == "WEBVTT\n"


def test_missing_video_file_is_an_error(tmp_path):
    video = {"src": str(tmp_path / "нет.mp4"), "title": "Ролик", "format": "9:16", "label": "схема"}
    with pytest.raises(FileNotFoundError):
        build_course(LAYER, {"routes": []}, TASKS, [], tmp_path / "out", extras={"lat.a": {"videos": [video]}})


def test_picture_size_is_known_before_it_loads(tmp_path):
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "a.svg").write_text('<svg viewBox="0 0 480 448.5"></svg>', encoding="utf-8")
    picture = {"id": "lat.a.i1", "step_id": "lat.a", "file": "pictures/a.svg", "alt": "а", "caption": "к", "label": "схема"}
    built = read_data(build_course(LAYER, {"routes": []}, TASKS, [picture], tmp_path / "out", tmp_path / "pics"))["steps"][0]["pictures"][0]
    assert (built["width"], built["height"]) == (480, 448)


def test_page_loads_every_script_it_ships(tmp_path):
    html = (build_course(LAYER, {"routes": []}, TASKS, [], tmp_path) / "index.html").read_text(encoding="utf-8")
    linked = re.findall(r'(?:src|href)="([^"#:]+)"', html)
    assert all((tmp_path / name).exists() for name in linked)
    assert {p.name for p in (tmp_path / "assets").glob("*.js")} == {Path(n).name for n in linked if n.startswith("assets/") and n.count("/") == 1 and n.endswith(".js")}


def test_page_has_one_live_region(tmp_path):
    html = (build_course(LAYER, {"routes": []}, TASKS, [], tmp_path) / "index.html").read_text(encoding="utf-8")
    assert html.count("aria-live") == 1
