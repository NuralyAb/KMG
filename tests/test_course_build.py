import json

from glava.course.build import build_course, course_data, paragraphs, reading_minutes, source_pages

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
