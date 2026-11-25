import json
from pathlib import Path

import pytest
from conftest import (
    CHAPTER,
    EMPTY_CHAPTER,
    ORIGIN,
    data_of,
    error_of,
    wait_for,
    write_json,
)
from fastapi.testclient import TestClient
from test_packages import good


def upload(client: TestClient, chapter: str = CHAPTER, **fields: object):
    return client.post("/api/reviews", data={"chapter": chapter}, files={"file": ("p.zip", good(**fields), "application/zip")}, headers=ORIGIN)


def test_reviews_are_listed_new_first_without_key_and_broken_files(client: TestClient) -> None:
    reviews = data_of(client.get("/api/reviews"))

    assert [r["package_id"] for r in reviews] == ["pkg_two", "pkg_one"]
    assert reviews[1]["chapter"] == CHAPTER and reviews[0]["chapter"] is None
    assert reviews[1]["counts"] == {"critical": 1, "significant": 0, "minor": 1}
    assert reviews[1]["created_at"].startswith("2025-10-09T")


def test_review_detail_has_complete_remarks(client: TestClient) -> None:
    review = data_of(client.get("/api/reviews/pkg_one"))

    assert review["remarks"][0] == {"target": "C1", "category": "other", "severity": "critical", "problem": "п", "fix": "и", "page_pdf": None,
                                    "quote": None}


def test_odd_remarks_are_skipped(client: TestClient, root: Path) -> None:
    write_json(root / "out" / "review" / "pkg_two.json", {"package_id": "pkg_two", "remarks": ["строка", {"severity": "huge"}, {"target": "C1"}]})

    assert data_of(client.get("/api/reviews/pkg_two"))["remarks"] == []


@pytest.mark.parametrize("package_id", ["nope", "key", "broken", "%2e%2e%2fkey", "..", "-x"])
def test_unknown_review_is_404(client: TestClient, package_id: str) -> None:
    error_of(client.get(f"/api/reviews/{package_id}"), 404)


def test_no_review_folder_gives_empty_list(client: TestClient, root: Path) -> None:
    (root / "out" / "review").rename(root / "out" / "other")

    assert data_of(client.get("/api/reviews")) == []


def test_upload_starts_review_run_with_extracted_package(client: TestClient, root: Path) -> None:
    run = data_of(upload(client, extra={"key.json": "{}"}), 201)

    assert (run["command"], run["chapter"], run["args"]) == ("review", CHAPTER, {"package_id": "pkg"})
    done = wait_for(lambda: (r := data_of(client.get(f"/api/runs/{run['id']}")))["state"] == "done" and r)
    argv = json.loads(done["log_tail"][0])["argv"]
    folder = Path(argv[3])
    assert argv[:3] == ["review", CHAPTER, "--package"]
    assert folder.parent == root / "work" / "review_uploads"
    assert sorted(p.name for p in folder.rglob("*") if p.is_file()) == ["F1.png", "package.json"]


def test_upload_for_unknown_chapter_is_404_and_leaves_nothing(client: TestClient, root: Path) -> None:
    error_of(upload(client, chapter="nope"), 404)

    assert not (root / "work" / "review_uploads").exists()


def test_bad_archive_is_422(client: TestClient) -> None:
    response = client.post("/api/reviews", data={"chapter": CHAPTER}, files={"file": ("p.zip", b"nope")}, headers=ORIGIN)

    assert error_of(response, 422)["code"] == "bad_package"


def test_upload_without_file_is_422(client: TestClient) -> None:
    error_of(client.post("/api/reviews", data={"chapter": CHAPTER}, headers=ORIGIN), 422)


def test_upload_while_chapter_is_busy_is_409_and_leaves_nothing(client: TestClient, root: Path) -> None:
    data_of(client.post("/api/runs", json={"command": "build", "chapter": CHAPTER}, headers=ORIGIN), 201)

    error_of(upload(client), 409)

    assert not list((root / "work").glob("review_uploads/*"))


def test_same_package_is_not_reviewed_twice_at_once(client: TestClient, root: Path) -> None:
    for chapter in (CHAPTER, EMPTY_CHAPTER):
        data_of(client.post("/api/runs", json={"command": "build", "chapter": chapter}, headers=ORIGIN), 201)
    registry = json.loads((root / "chapters.json").read_text(encoding="utf-8"))
    entry = registry["chapters"][CHAPTER]
    write_json(root / "chapters.json", {**registry, "chapters": {**registry["chapters"], "c3": entry, "c4": entry}})
    data_of(upload(client, chapter="c3"), 201)

    error_of(upload(client, chapter="c4"), 409)

    assert len(list((root / "work" / "review_uploads").iterdir())) == 1
