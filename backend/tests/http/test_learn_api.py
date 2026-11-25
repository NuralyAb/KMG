"""Ученик видит только опубликованное, автор входит по паролю, публикация — снимок, который пересборка не меняет."""

import json
import os
from dataclasses import replace
from typing import Any

import pytest
from conftest import (
    BASE_URL,
    CHAPTER,
    EMPTY_CHAPTER,
    ORIGIN,
    data_of,
    error_of,
    write_json,
)
from fastapi.testclient import TestClient
from glava.entrypoints.http.app import MODULES, create_app
from glava.modules.access.service import MAX_FAILURES, WINDOW_S, Access, is_public
from glava.modules.runs.process import child_env
from glava.shared.http.errors import ApiError
from glava.shared.http.settings import ConfigError, settings_from_env

PASSWORD = "длинный пароль"


def write_course(root, title: str = "Курс", **over: Any) -> None:
    nodes = json.loads((root / "work" / CHAPTER / "layer.json").read_text(encoding="utf-8"))["nodes"]
    steps = [{"id": n["id"], "order": n["order"], "short_title": n["short_title"], "minutes": 2, "claims": n["claims"], "tasks": [{"id": "t"}]} for n in nodes]
    data = {"id": CHAPTER, "title": title, "book": "Книга", "parts": [{"title": "Часть", "nodes": [s["id"] for s in steps]}], "steps": steps, **over}
    (root / "out" / CHAPTER / "data.js").write_text(f"window.COURSE={json.dumps(data, ensure_ascii=False)};", encoding="utf-8")


@pytest.fixture
def course(root):
    write_course(root)


def publish(client, accepted=None, chapter=CHAPTER):
    if accepted is None:
        accepted = [c["code"] for c in data_of(client.get(f"/api/chapters/{chapter}/publication"))["checks"]]
    return client.post(f"/api/chapters/{chapter}/publication", json={"accepted": accepted}, headers=ORIGIN)


# ---------- публикация
def test_nothing_is_visible_before_publication(client, course):
    assert data_of(client.get("/api/learn/courses")) == []
    error_of(client.get(f"/api/learn/courses/{CHAPTER}"), 404)
    error_of(client.get(f"/learn/{CHAPTER}/index.html"), 404)


def test_published_course_reaches_the_learner(client, course):
    assert data_of(publish(client))["is_current"] is True
    found = data_of(client.get("/api/learn/courses"))
    assert [(c["id"], c["title"], c["steps"], c["minutes"], c["tasks"]) for c in found] == [(CHAPTER, "Курс", 3, 6, 3)]
    assert [s["title"] for s in data_of(client.get(f"/api/learn/courses/{CHAPTER}"))["parts"][0]["steps"]] == ["first", "second", "third"]
    assert client.get(f"/learn/{CHAPTER}/").text == "<!doctype html><p>курс</p>"
    assert data_of(client.get(f"/api/chapters/{CHAPTER}"))["published_at"]


def test_learner_gets_no_author_data(client, course):
    data_of(publish(client))
    body = client.get(f"/api/learn/courses/{CHAPTER}").text
    assert not any(word in body for word in ("accepted", "sha256", "cost", "quote"))


def test_rebuild_does_not_change_what_learners_see(client, root, course):
    data_of(publish(client))
    (root / "out" / CHAPTER / "index.html").write_text("сломано", encoding="utf-8")
    write_course(root, "Новое название")
    assert "курс" in client.get(f"/learn/{CHAPTER}/").text
    assert data_of(client.get("/api/learn/courses"))[0]["title"] == "Курс"
    assert data_of(client.get(f"/api/chapters/{CHAPTER}/publication"))["is_current"] is False
    data_of(publish(client))
    assert data_of(client.get("/api/learn/courses"))[0]["title"] == "Новое название"


def test_author_must_accept_every_remark(client, root, course):
    checks = data_of(client.get(f"/api/chapters/{CHAPTER}/publication"))["checks"]
    assert {c["code"] for c in checks} == {"layer_issues:3", "no_audit:1", "no_verify:1"}
    error_of(publish(client, []), 409)
    assert data_of(publish(client))["accepted"] == [c["text"] for c in checks]


def test_more_remarks_need_a_new_consent(client, root, course):
    old = [c["code"] for c in data_of(client.get(f"/api/chapters/{CHAPTER}/publication"))["checks"]]
    write_json(root / "work" / CHAPTER / "layer_report.json", {"issues": {"x": ["а"] * 9}})
    assert "9" in error_of(publish(client, old), 409)["message"]


def test_trust_findings_are_listed(client, root, course):
    import hashlib

    work = root / "work" / CHAPTER
    digest = hashlib.sha256((work / "layer.json").read_bytes()).hexdigest()
    write_json(work / "audit.json", {"layer_sha256": digest, "flagged": [{}, {}], "needs_scan": 1})
    write_json(work / "trust.json", {"layer_sha256": digest, "claims": {"contradicts": 1, "no": 0, "unchecked": 2}, "prose": {"contradicts": 3}})
    codes = {c["code"] for c in data_of(client.get(f"/api/chapters/{CHAPTER}/publication"))["checks"]}
    assert codes == {"layer_issues:3", "flagged:2", "needs_scan:1", "contradicts:4", "unchecked:2"}


def test_course_of_another_layer_is_not_published(client, root, course):
    layer = root / "work" / CHAPTER / "layer.json"
    data = json.loads(layer.read_text(encoding="utf-8"))
    data["nodes"][0]["claims"][0]["quote"] = "другая цитата"
    write_json(layer, data)
    assert "другой версии слоя" in data_of(client.get(f"/api/chapters/{CHAPTER}/publication"))["problem"]
    error_of(publish(client, []), 409)


@pytest.mark.parametrize("text", ["", "window.X = 1", "window.COURSE={", "window.COURSE=[]", 'window.COURSE={"steps": []};', "alert(1);window.COURSE={}"])
def test_broken_course_is_not_published(client, root, text):
    (root / "out" / CHAPTER / "data.js").write_text(text, encoding="utf-8")
    error_of(publish(client, []), 409)
    assert not list((root / "published").glob("*"))


def test_course_of_another_chapter_is_not_published(client, root):
    write_course(root, id=EMPTY_CHAPTER)
    error_of(publish(client, []), 409)


def test_unbuilt_and_unknown_chapters(client):
    error_of(publish(client, [], EMPTY_CHAPTER), 409)
    error_of(publish(client, [], "nope"), 404)
    error_of(client.delete(f"/api/chapters/{CHAPTER}/publication", headers=ORIGIN), 404)


def test_unpublish_hides_everything(client, course):
    data_of(publish(client))
    data_of(client.delete(f"/api/chapters/{CHAPTER}/publication", headers=ORIGIN))
    assert data_of(client.get("/api/learn/courses")) == []
    error_of(client.get(f"/learn/{CHAPTER}/index.html"), 404)


def test_snapshot_holds_only_page_files(client, root, course):
    outside = root / "secret.txt"
    outside.write_text("секрет", encoding="utf-8")
    os.symlink(outside, root / "out" / CHAPTER / "link.txt")
    data_of(publish(client))
    names = {p.relative_to(root / "published" / CHAPTER).as_posix() for p in (root / "published" / CHAPTER).rglob("*") if p.is_file()}
    assert names == {"index.html", "data.js", "pictures/first_1.svg", "videos/v1.mp4", "videos/v1.srt"}
    assert {p.name for p in (root / "published").iterdir()} == {CHAPTER, f"{CHAPTER}.json"}


@pytest.mark.parametrize("path", ["../chapters.json", "%2e%2e/%2e%2e/chapters.json", "key.json", "..%5cx"])
def test_learner_cannot_leave_the_snapshot(client, course, path):
    data_of(publish(client))
    assert client.get(f"/learn/{CHAPTER}/{path}").status_code == 404


def test_published_chapter_stays_in_the_library(client, root):
    chapter = "lib_0000aaaa"
    write_json(root / "library" / "chapters.json", {"chapters": {chapter: {"title": "x", "domain": "general", "pages": [[1, 1]], "source": "src_000000000000"}}})
    (root / "published" / chapter).mkdir(parents=True)
    (root / "published" / chapter / "index.html").write_text("к", encoding="utf-8")
    write_json(root / "published" / f"{chapter}.json", {"id": chapter, "title": "x", "book": "", "steps": 1, "minutes": 1, "tasks": 0, "parts": [], "published_at": "2026"})
    error_of(client.delete(f"/api/library/chapters/{chapter}", headers=ORIGIN), 409)


# ---------- вход
@pytest.fixture
def locked(settings, root):
    write_course(root)
    with TestClient(create_app(settings), base_url=BASE_URL) as open_client:
        data_of(publish(open_client))
    with TestClient(create_app(replace(settings, admin_password=PASSWORD)), base_url=BASE_URL, raise_server_exceptions=False) as client:
        yield client


def login(client, password=PASSWORD):
    return client.post("/api/auth/login", json={"password": password}, headers=ORIGIN)


def test_without_a_password_everyone_is_the_author(client):
    assert data_of(client.get("/api/auth/me")) == {"role": "admin", "protected": False}
    error_of(login(client), 409)


def test_every_route_is_closed_unless_opened_for_learners(locked):
    """Обходит все адреса приложения: новый адрес по умолчанию закрыт."""
    routes = [r for module in MODULES for r in module.router.routes]
    assert len(routes) > 39
    opened = set()
    for route in routes:
        for method in getattr(route, "methods", None) or ():
            path = route.path.replace("{chapter_id}", CHAPTER).replace("{course_id}", CHAPTER).replace("{path:path}", "index.html")
            for name in ("{node_id}", "{run_id}", "{package_id}", "{source_id}", "{book_id}", "{number}"):
                path = path.replace(name, "1")
            if method != "HEAD" and locked.request(method, path, headers=ORIGIN, json={}).status_code != 401:
                opened.add((method, route.path))
    assert opened == {("GET", "/api/learn/courses"), ("GET", "/api/learn/courses/{course_id}"), ("GET", "/learn/{course_id}/{path:path}"),
                      ("GET", "/api/auth/me"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout")}


@pytest.mark.parametrize("path", ["/api/learn/../chapters", "/api/learn/%2e%2e/chapters", "/api/learning", "/learnx", "//api/chapters", "/api/learn/..%2fchapters", "/API/chapters", f"/course/{CHAPTER}/index.html"])
def test_tricks_with_paths_do_not_open_author_data(locked, path):
    response = locked.get(path)
    assert response.status_code in (401, 404) and "cost_usd" not in response.text


def test_learner_sees_courses_without_login(locked):
    assert data_of(locked.get("/api/auth/me")) == {"role": "learner", "protected": True}
    assert len(data_of(locked.get("/api/learn/courses"))) == 1
    assert locked.get(f"/learn/{CHAPTER}/").status_code == 200


def test_login_and_logout(locked):
    response = login(locked)
    cookie = response.headers["set-cookie"].lower()
    assert data_of(response)["role"] == "admin" and "httponly" in cookie and "samesite=strict" in cookie and PASSWORD not in cookie
    assert data_of(locked.get("/api/chapters"))
    token = locked.cookies.get("glava_admin")
    data_of(locked.post("/api/auth/logout", headers=ORIGIN))
    locked.cookies.set("glava_admin", token)
    error_of(locked.get("/api/chapters"), 401)


@pytest.mark.parametrize("cookie", ["", "x", "a" * 5000, 'glava_admin="', "\\x00"])
def test_forged_session_is_refused(locked, cookie):
    error_of(locked.get("/api/chapters", headers={"Cookie": f"glava_admin={cookie}"}), 401)


def test_login_only_from_own_page(locked):
    error_of(locked.post("/api/auth/login", json={"password": PASSWORD}, headers={"Origin": "http://evil.example"}), 400)


def test_guessing_is_slowed_down():
    now = [0.0]
    access = Access(PASSWORD, lambda: now[0])
    for _ in range(MAX_FAILURES):
        with pytest.raises(ApiError, match="не подошёл"):
            access.login("неверный")
    with pytest.raises(ApiError, match="подождите"):
        access.login(PASSWORD)
    now[0] += WINDOW_S
    assert access.is_admin(access.login(PASSWORD))


def test_session_ends():
    now = [0.0]
    access = Access(PASSWORD, lambda: now[0])
    token = access.login(PASSWORD)
    now[0] += 13 * 3600
    assert not access.is_admin(token) and not access.is_admin(None)


def test_password_is_neither_short_nor_shown_nor_passed_on():
    with pytest.raises(ConfigError):
        settings_from_env({"GLAVA_ADMIN_PASSWORD": "1234"})
    assert PASSWORD not in repr(settings_from_env({"GLAVA_ADMIN_PASSWORD": PASSWORD}))
    assert "GLAVA_ADMIN_PASSWORD" not in child_env({"GLAVA_ADMIN_PASSWORD": PASSWORD})


@pytest.mark.parametrize(("path", "expected"), [("/api/learn", True), ("/api/learn/x", True), ("/api/learnx", False), ("/learn/a", True), ("/api", False), ("/", False)])
def test_public_paths(path, expected):
    assert is_public(path) is expected
