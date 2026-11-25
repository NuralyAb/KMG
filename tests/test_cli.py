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
