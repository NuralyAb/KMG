import json
from pathlib import Path
from typing import Any

import pytest
from conftest import data_of, error_of
from fastapi.testclient import TestClient
from glava.modules.books.splitter import merged_ranges, split_book

ORIGIN = {"Origin": "http://127.0.0.1:5190"}
MD = """# Учебник
<!-- page 1 -->
# Глава I
## НАЧАЛО
текст
<!-- page 2 -->
текст
### § 1. Первый
<!-- page 3 -->
# § 2. Второй
текст
<!-- page 4 -->
# Глава II
## КОНЕЦ
<!-- page 5 -->
текст
"""


def upload(client: TestClient, name: str = "Книга о пластах.md", md: str | bytes = MD, pdf: bytes | None = None) -> Any:
    files: dict[str, Any] = {"file": (name, md if isinstance(md, bytes) else md.encode())}
    if pdf is not None:
        files["pdf"] = ("k.pdf", pdf)
    return client.post("/api/books", files=files, headers=ORIGIN)


def test_split_uses_numbers_not_hashes() -> None:
    found = [(s.title, s.level, s.first, s.last) for s in split_book(MD)]
    assert found == [("Глава I. НАЧАЛО", 1, 1, 3), ("§ 1. Первый", 2, 2, 2), ("§ 2. Второй", 2, 3, 3), ("Глава II. КОНЕЦ", 1, 4, 5)]


def test_split_english_and_running_header() -> None:
    english = "<!-- page 1 -->\n# Chapter 1\n## Seismic\n<!-- page 2 -->\n# Chapter 2. Logs\n"
    assert [(s.title, s.first, s.last) for s in split_book(english)] == [("Chapter 1. Seismic", 1, 1), ("Chapter 2. Logs", 2, 2)]
    header = "".join(f"<!-- page {p} -->\n1.2. Дельты\nтекст\n" for p in (1, 2, 3)) + "<!-- page 4 -->\n1.3. Озёра\nтекст\n<!-- page 5 -->\n1.3. Озёра\n<!-- page 6 -->\n1.3. Озёра\n"
    assert [(s.title, s.first, s.last) for s in split_book(header)] == [("1.2. Дельты", 1, 3), ("1.3. Озёра", 4, 6)]


def test_book_without_headings_or_pages() -> None:
    assert split_book("просто текст") == []
    assert split_book("<!-- page 1 -->\nтекст") == []
    assert merged_ranges([(5, 6), (1, 2), (3, 3)]) == [[1, 3], [5, 6]]


def test_upload_shows_contents_and_creates_a_chapter(client: TestClient, root: Path) -> None:
    (root / "domain" / "geology").mkdir(parents=True, exist_ok=True)
    book = data_of(upload(client, pdf=b"%PDF-1.4 x"), 201)
    detail = data_of(client.get(f"/api/books/{book['id']}"))
    assert book["uploaded"] and book["has_pdf"] and detail["last_page"] == 5 and len(detail["sections"]) == 4

    made = data_of(client.post(f"/api/books/{book['id']}/chapters", json={"title": "Начало", "pages": [[1, 2], [3, 3]]}, headers=ORIGIN), 201)
    info = json.loads((root / "chapters.json").read_text(encoding="utf-8"))["chapters"][made["id"]]
    assert info["pages"] == [[1, 3]] and info["root"] == "books" and info["pdf"].endswith(".pdf")
    assert made["id"] in {c["id"] for c in data_of(client.get("/api/chapters"))}
    error_of(client.post(f"/api/books/{book['id']}/chapters", json={"title": "Ещё раз", "pages": [[1, 3]]}, headers=ORIGIN), 409)


def test_two_chapters_of_one_book_get_different_prefixes(client: TestClient, root: Path) -> None:
    (root / "domain" / "geology").mkdir(parents=True, exist_ok=True)
    book = data_of(upload(client), 201)["id"]
    ids = [data_of(client.post(f"/api/books/{book}/chapters", json={"title": "Глава", "pages": [[p, p]]}, headers=ORIGIN), 201)["id"] for p in (1, 2)]
    chapters = json.loads((root / "chapters.json").read_text(encoding="utf-8"))["chapters"]
    assert len({chapters[i]["prefix"] for i in ids}) == 2


@pytest.mark.parametrize("body", [
    {"title": "Глава", "pages": []}, {"title": "Глава", "pages": [[3, 1]]}, {"title": "Глава", "pages": [[1, 99]]}, {"title": "x", "pages": [[1, 2]]},
    {"title": "Глава", "pages": [[1, 2]], "domain": "../x"}, {"title": "Глава", "pages": [[1]]}, {"title": "Глава", "pages": [[1, 2]], "file": "x"},
])
def test_wrong_chapter_is_refused(client: TestClient, root: Path, body: dict[str, Any]) -> None:
    (root / "domain" / "geology").mkdir(parents=True, exist_ok=True)
    before = (root / "chapters.json").read_text(encoding="utf-8")
    book = data_of(upload(client), 201)["id"]
    error_of(client.post(f"/api/books/{book}/chapters", json=body, headers=ORIGIN), 422)
    assert (root / "chapters.json").read_text(encoding="utf-8") == before


@pytest.mark.parametrize(("name", "md", "pdf"), [
    ("a.txt", MD, None), ("key.md", MD, None), ("a.md", "без страниц", None), ("a.md", b"\xff\xfe\x00", None), ("a.md", MD, b"MZ"),
])
def test_wrong_upload_is_refused(client: TestClient, root: Path, name: str, md: str | bytes, pdf: bytes | None) -> None:
    error_of(upload(client, name, md, pdf), 422)
    assert not list((root / "books").glob("*")) if (root / "books").exists() else True


def test_path_in_a_name_stays_inside_books(client: TestClient, root: Path) -> None:
    data_of(upload(client, "../../evil.md"), 201)
    assert [p.name for p in (root / "books").iterdir()] == ["evil.md"]


def test_same_name_other_text_is_a_conflict(client: TestClient) -> None:
    data_of(upload(client, "a1.md"), 201)
    data_of(upload(client, "a1.md"), 201)
    error_of(upload(client, "a1.md", MD + "ещё"), 409)


def test_unknown_book_is_404(client: TestClient) -> None:
    error_of(client.get("/api/books/nope"), 404)
