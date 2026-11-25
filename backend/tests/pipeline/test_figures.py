"""Рисунки со скана: прочтение модели заменяет описание распознавателя, расхождения идут в лист опечаток, повтор не платит."""

import json

import pytest
from glava.modules.figure_reading.reading import (
    figure_errata,
    figure_pages,
    read_figures,
    reading_issues,
    reading_text,
    with_readings,
)
from glava.modules.llm.client import Reply
from glava.modules.source_text.api import parse_units
from glava.pipeline.chapter import Chapter, errata_of, load_chapter
from glava.shared import paths
from glava.shared.json_files import save

RECOGNISER = "━━━ FORMAT 7: NOMOGRAM / ПАЛЕТКА ━━━\n\nЛевая ось: ρп, Ом·м — логарифмический масштаб, диапазон от 1 до 10.\n\nКривая 20 убывает быстрее всех."
MD = (f"<!-- page 5 -->\nТекст страницы про палетку.\n\n----\n{RECOGNISER}\n----\n\nРис. 3. Палетка ρп = f(kп).\n\n"
      "<!-- page 6 -->\nРис. 4. Фото керна.\n\nДругой текст.\n")
READING = {"unit_id": "p005.02", "caption_unit": "p005.03", "figure": "3", "what": "Палетка для оценки насыщения.",
           "axes": [{"name": "ρп, Ом·м", "where": "слева, вверх", "scale": "логарифмическая", "ticks": "1, 2, 5, 10, 20, 50"}],
           "curves": [{"label": "20", "meaning": "шифр 20", "behaviour": "верхняя и самая пологая"}], "regions": [{"label": "I", "meaning": "безводная нефть"}],
           "legend": [], "numbers": [{"what": "ρп у правого края", "value": "40"}],
           "mismatches": [{"recogniser": "диапазон от 1 до 10", "scan": "диапазон от 1 до 50", "note": "потеряны деления"}], "unreadable": []}
PHOTO = {"unit_id": "p006.01", "caption_unit": None, "figure": "4", "what": "Фото керна: тонкие слои.", "axes": [], "curves": [], "regions": [],
         "legend": [], "numbers": [], "mismatches": [], "unreadable": []}


class Fake:
    name, model = "fake", "fake"

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def ask(self, system, prompt, files=()):
        self.asked.append((prompt, list(files)))
        page = int(prompt.split()[2])
        return Reply(json.dumps(self.answers[page], ensure_ascii=False), "fake", 10, 10, 0.01)


def units():
    return parse_units({5: MD.split("<!-- page 6 -->")[0].split("-->", 1)[1], 6: MD.split("<!-- page 6 -->")[1]})


def test_pages_pair_descriptions_with_captions():
    found = {f.page: f for f in figure_pages(units())}
    assert [u.unit_id for u in found[5].descriptions] == ["p005.02"]
    assert [u.unit_id for u in found[5].captions] == ["p005.03"]
    assert [u.unit_id for u in found[5].nearby] == ["p006.01"]
    assert found[6].descriptions == () and "Подписи на соседних страницах" in found[6].prompt


def test_reading_must_cover_the_page_and_quote_the_recogniser():
    page = figure_pages(units())[0]
    assert reading_issues({"figures": [READING]}, page) == []
    assert any("не прочитано" in i for i in reading_issues({"figures": []}, page))
    wrong = {**READING, "mismatches": [{"recogniser": "такого куска нет в описании", "scan": "x", "note": ""}]}
    assert any("дословно" in i for i in reading_issues({"figures": [wrong]}, page))
    alone = {**READING, "caption_unit": None}
    assert any("подпись p005.03" in i for i in reading_issues({"figures": [alone]}, page))
    assert reading_issues({"figures": [alone], "not_here": ["p005.03"]}, page) == []


def test_bad_mismatch_is_dropped_and_the_reading_kept(tmp_path):
    image = tmp_path / "p.png"
    image.write_bytes(b"png")
    page = figure_pages(units())[0]
    mixed = {**READING, "mismatches": [*READING["mismatches"], {"recogniser": "выдуманный кусок описания", "scan": "y", "note": ""}]}
    fake = Fake({5: {"figures": [mixed]}})
    found, replies = read_figures(fake, "s", page, image)
    assert [m["scan"] for m in found[0]["mismatches"]] == ["диапазон от 1 до 50"]
    assert found[0]["page"] == 5 and found[0]["source"] == units()[1].text
    assert fake.asked[0][1] == [image] and len(replies) == 2


def test_reading_replaces_the_recogniser_and_stays_approximate():
    reading = {**READING, "page": 5, "source": units()[1].text}
    photo = {**PHOTO, "page": 6, "source": units()[3].text}
    out = with_readings(units(), [reading, photo])
    figure = next(u for u in out if u.unit_id == "p005.02")
    assert figure.by_recogniser and figure.text == reading_text(reading)
    assert "диапазон от 1 до 10" not in figure.text and "1, 2, 5, 10, 20, 50" in figure.text
    assert "≈ 40" in figure.text and "приблизительно" in figure.text
    # у рисунка без описания прочтение встаёт после подписи отдельной единицей модели
    ids = [u.unit_id for u in out]
    assert ids[ids.index("p006.01") + 1] == "p006.01f" and out[ids.index("p006.01f")].by_recogniser
    # md изменился: старое прочтение не ложится на другой рисунок
    assert with_readings(units(), [{**reading, "source": "старый текст"}]) == units()


def test_mismatches_become_recognition_errata():
    entries = figure_errata([{**READING, "page": 5}])
    assert entries == [{"page": 5, "md": "диапазон от 1 до 10", "scan": "диапазон от 1 до 50", "kind": "recognition",
                        "note": "рис. 3; потеряны деления; прочитано моделью по скану"}]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    import pymupdf

    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    (tmp_path / "b.md").write_text(MD, encoding="utf-8")
    with pymupdf.open() as pdf:
        for _ in range(6):
            pdf.new_page(width=200, height=200)
        pdf.save(tmp_path / "b.pdf")
    info = {"file": "b.md", "pdf": "b.pdf", "root": ".", "pages": [[5, 6]], "prefix": "b", "domain": "own", "title": "t", "book": "b"}
    save(tmp_path / "chapters.json", {"root": ".", "pdf_root": ".", "chapters": {"b": info}})
    return tmp_path


def test_build_figures_caches_and_feeds_the_layer(workspace):
    from glava.pipeline.steps.figures import build_figures

    fake = Fake({5: {"figures": [READING]}, 6: {"figures": [PHOTO]}})
    chapter = load_chapter("b")
    assert chapter.recognised == () and chapter.source_units == chapter.units
    build_figures(chapter, fake)
    assert len(fake.asked) == 2
    build_figures(load_chapter("b"), fake)
    assert len(fake.asked) == 2, "повтор не должен спрашивать модель"
    again = load_chapter("b")
    by_id = {u.unit_id: u for u in again.units}
    assert "1, 2, 5, 10, 20, 50" in by_id["p005.02"].text and "p006.01f" in by_id
    assert {u.unit_id: u.text for u in again.source_units}["p005.02"] == units()[1].text
    assert [e["scan"] for e in errata_of(again)] == ["диапазон от 1 до 50"]
    assert (workspace / "metrics.csv").read_text(encoding="utf-8").count("figures") == 1


def test_without_pdf_nothing_is_asked(tmp_path, monkeypatch):
    from glava.pipeline.steps.figures import build_figures

    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    fake = Fake({})
    assert build_figures(Chapter("c", "c", "t", "b", tmp_path, tuple(units()), "c.md"), fake) == [] and fake.asked == []
