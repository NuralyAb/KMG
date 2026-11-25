"""Команды собираются и читают реестр глав."""

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
    chapter = cli.load_chapter("latyshova_gl5_par17-20")
    text = cli.routing_context(chapter)
    assert "log — планшет ГИС" in text
    assert "well_tool_curve" in text
    assert "Видео" in text or "видео" in text
