"""Команды собираются и читают реестр глав."""

from pathlib import Path

from glava import cli


def test_course_is_built_without_optional_stages(tmp_path, monkeypatch):
    # Arrange: есть только слой, маршрутов, заданий и рисунков ещё нет
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    chapter = cli.Chapter("demo", "dm", "Глава", "Книга", tmp_path, (), "demo.md")
    layer = {"chapter": "demo", "title": "Глава", "book": "Книга", "generated_by": "x/y", "parts": [], "nodes": []}
    cli.save(chapter.work / "layer.json", layer)

    # Act
    out = cli.build_site(chapter)

    # Assert
    assert (out / "index.html").exists()
    assert (out / "assets" / "course.js").stat().st_size > 0


def test_read_or_returns_default_for_missing_file(tmp_path):
    assert cli.read_or(tmp_path / "none.json", {"routes": []}) == {"routes": []}


def test_manual_errata_survive_and_join_the_recognised_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    chapter = cli.Chapter("demo", "dm", "Глава", "Книга", tmp_path, (), "demo.md")
    cli.save(chapter.errata_file, {"chapter": "demo", "entries": [{"page": 1, "md": "а", "scan": "б", "kind": "recognition"}]})
    assert len(cli.errata_of(chapter)) == 1
    cli.save(chapter.errata_file.with_suffix(".manual.json"), {"entries": [{"page": 2, "md": "в", "scan": "г", "kind": "suspect"}]})
    assert [e["page"] for e in cli.errata_of(chapter)] == [1, 2]


def test_routing_sees_what_templates_show_and_the_difficulty_types():
    domain = Path(__file__).resolve().parents[1] / "domain" / "geology"
    chapter = cli.Chapter("demo", "dm", "Глава", "Книга", domain, (), "demo.md")
    text = cli.routing_context(chapter)
    assert "log — планшет ГИС" in text
    assert "well_tool_curve" in text
    assert "Видео" in text or "видео" in text


def test_blocks_of_a_node_reach_the_built_course(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    chapter = cli.Chapter("demo", "dm", "Глава", "Книга", tmp_path, (), "demo.md")
    blocks = {"procedure": [{"text": "Снимите отсчёт.", "pages": [5], "claim_id": "dm.a#c1"}], "numbers": [{"text": "Порог 4.", "page": 5, "claim_id": "dm.a#c1"}],
              "formulas": [{"tex": "a=b", "page": 5, "claim_id": "dm.a#c1", "legend": [{"symbol": "a", "meaning": "величина", "unit": ""}], "errata": None}],
              "tables": [{"title": "Таблица", "page": 5, "header": ["а"], "rows": [["1"]], "corrections": []}]}
    text = {"text": "Суть. Вторая.", "by_model": True}
    node = {"id": "dm.a", "order": 1, "title": "Полное название", "short_title": "Короткое имя шага", "pages": [5], "claims": [], "terms_introduced": [], "glossary": [],
            "layers": {**{k: text for k in ("topic", "main", "mechanism", "practice", "nuances")}, "deeper": []}, "why_here": text, "difficulty": {"primary": "И", "secondary": None},
            "threshold": False, "links": [], "needs_scan": [], **blocks}
    layer = {"chapter": "demo", "title": "Глава", "book": "Книга", "generated_by": "x/y", "parts": [{"title": "Ч", "nodes": ["dm.a"]}], "nodes": [node]}
    cli.save(chapter.work / "layer.json", layer)

    data = (cli.build_site(chapter) / "data.js").read_text(encoding="utf-8")

    for found in ("Снимите отсчёт.", "Порог 4.", "величина", "Таблица"):
        assert found in data
