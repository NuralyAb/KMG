import sys
from pathlib import Path

import pytest
from conftest import CHAPTER, EMPTY_CHAPTER, data_of, error_of
from fastapi.testclient import TestClient
from glava.modules.publishing.course_files import resolve_course_file
from glava.shared.http.errors import ApiError

if sys.platform == "win32":
    import _winapi


@pytest.mark.parametrize(("path", "media_type"), [
    ("index.html", "text/html"), ("data.js", "text/javascript"), ("pictures/first_1.svg", "image/svg+xml"), ("videos/v1.mp4", "video/mp4"),
    ("videos/v1.srt", "application/x-subrip"), ("videos/v1.passport.json", "application/json"),
])
def test_course_files_have_fixed_media_types(client: TestClient, path: str, media_type: str) -> None:
    response = client.get(f"/course/{CHAPTER}/{path}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media_type)


def test_folder_address_opens_index(client: TestClient) -> None:
    assert "курс" in client.get(f"/course/{CHAPTER}/").text
    assert "курс" in client.get(f"/course/{CHAPTER}").text


def test_video_supports_range_requests(client: TestClient) -> None:
    response = client.get(f"/course/{CHAPTER}/videos/v1.mp4", headers={"Range": "bytes=2-4"})

    assert (response.status_code, response.text) == (206, "234")


@pytest.mark.parametrize("path", [
    "../../chapters.json", "..%2f..%2fchapters.json", "%2e%2e/%2e%2e/chapters.json", "..%5c..%5cchapters.json", "pictures/../../../chapters.json",
    "key.json", "KEY.JSON", "key.json%20", "key.json.", "key.json::$DATA", ".hidden", "C:/Windows/win.ini", "%00", "nul", "pictures", "нет.html",
    "pictures//first_1.svg/..",
])
def test_everything_outside_course_folder_is_404(client: TestClient, path: str) -> None:
    response = client.get(f"/course/{CHAPTER}/{path}")

    error_of(response, 404)


@pytest.mark.parametrize("path", [
    "../../chapters.json", "..\\..\\chapters.json", "pictures/../../../chapters.json", "/etc/passwd", "C:\\Windows\\win.ini", "\\\\host\\share\\x",
    "key.json", "Key.json.", "key.json ", "key.json::$DATA", ".hidden", "\x00", "a//b", "./index.html",
])
def test_resolver_itself_rejects_dangerous_paths(root: Path, path: str) -> None:
    with pytest.raises(ApiError) as caught:
        resolve_course_file(root / "out" / CHAPTER, path)

    assert caught.value.status == 404


def test_course_of_unknown_or_unbuilt_chapter_is_404(client: TestClient) -> None:
    error_of(client.get("/course/nope/index.html"), 404)
    error_of(client.get("/course/review/pkg_one.json"), 404)
    error_of(client.get(f"/course/{EMPTY_CHAPTER}/index.html"), 404)


def test_link_leading_outside_is_rejected(root: Path) -> None:
    link = root / "out" / CHAPTER / "jump"
    if sys.platform == "win32":
        _winapi.CreateJunction(str(root), str(link))  # соединение папок не требует прав администратора
    else:
        link.symlink_to(root)
    assert (link / "chapters.json").is_file()

    with pytest.raises(ApiError):
        resolve_course_file(root / "out" / CHAPTER, "jump/chapters.json")


def test_api_stays_available_after_rejections(client: TestClient) -> None:
    assert data_of(client.get("/api/health"))["status"] == "ok"
