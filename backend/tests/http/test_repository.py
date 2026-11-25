import json
from pathlib import Path

import pytest
from conftest import CHAPTER, EMPTY_CHAPTER, write_json
from glava.modules.catalog.repository import Repository
from glava.shared.http.errors import ApiError
from glava.shared.json_store import JsonStore


@pytest.fixture
def repository(root: Path) -> Repository:
    return Repository(root)


def test_missing_file_is_none(tmp_path: Path) -> None:
    assert JsonStore().read(tmp_path / "нет.json") is None


def test_half_written_file_is_none_when_nothing_was_read_before(tmp_path: Path) -> None:
    path = tmp_path / "layer.json"
    path.write_text('{"nodes": [', encoding="utf-8")

    assert JsonStore(retry_delay=0).read(path) is None


def test_half_written_file_returns_last_good_version(tmp_path: Path) -> None:
    store = JsonStore(retry_delay=0)
    path = write_json(tmp_path / "layer.json", {"nodes": [1]})
    store.read(path)
    path.write_text('{"nodes": [1, ', encoding="utf-8")

    assert store.read(path) == {"nodes": [1]}


def test_changed_file_is_read_again(tmp_path: Path) -> None:
    store = JsonStore()
    path = write_json(tmp_path / "a.json", {"v": 1}, mtime=1000)
    store.read(path)
    write_json(path, {"v": 2}, mtime=2000)

    assert store.read(path) == {"v": 2}


@pytest.mark.parametrize("name", ["key.json", "KEY.JSON", "ctrl_key.json"])
def test_key_file_is_never_read(tmp_path: Path, name: str) -> None:
    path = write_json(tmp_path / name, {"answers": 1})

    assert JsonStore().read(path) is None


def test_root_that_is_not_an_object_is_treated_as_missing(root: Path) -> None:
    write_json(root / "work" / CHAPTER / "layer.json", ["не", "слой"])

    assert Repository(root).nodes(CHAPTER) == []


def test_chapter_info_expands_page_ranges(repository: Repository) -> None:
    info = repository.chapter(CHAPTER)

    assert info.pages == (10, 11, 12, 20, 21)
    assert info.domain == "geology"


@pytest.mark.parametrize("chapter_id", ["..", "../alpha_gl1", "nope", "", "-x", "alpha_gl1/..", "a b"])
def test_unknown_or_unsafe_chapter_is_404(repository: Repository, chapter_id: str) -> None:
    with pytest.raises(ApiError) as caught:
        repository.chapter(chapter_id)

    assert caught.value.status == 404


def test_registry_entry_with_unsafe_names_is_skipped(root: Path) -> None:
    data = json.loads((root / "chapters.json").read_text(encoding="utf-8"))
    entry = data["chapters"][CHAPTER]
    write_json(root / "chapters.json", {**data, "chapters": {"../up": entry, "bad_domain": {**entry, "domain": "../.."}, CHAPTER: entry}})

    assert [c.id for c in Repository(root).chapters()] == [CHAPTER]


def test_missing_registry_gives_readable_error(tmp_path: Path) -> None:
    with pytest.raises(ApiError) as caught:
        Repository(tmp_path).chapters()

    assert caught.value.status == 500
    assert "chapters.json" in caught.value.message


def test_chapter_without_files_has_empty_data(repository: Repository) -> None:
    assert repository.nodes(EMPTY_CHAPTER) == []
    assert repository.coverage(EMPTY_CHAPTER) == []
    assert repository.errata(EMPTY_CHAPTER) == []
    assert repository.tasks(EMPTY_CHAPTER) == []
    assert repository.issue_count(EMPTY_CHAPTER) == 0


def test_broken_metrics_rows_are_skipped(repository: Repository) -> None:
    rows = repository.metrics()

    assert [(r.chapter, r.stage) for r in rows] == [(CHAPTER, "layer"), (CHAPTER, "tasks"), (EMPTY_CHAPTER, "review")]
    assert rows[1].person_minutes == 5.0 and rows[0].money_usd == 1.25


def test_missing_metrics_file_is_empty(tmp_path: Path) -> None:
    assert Repository(tmp_path).metrics() == []
