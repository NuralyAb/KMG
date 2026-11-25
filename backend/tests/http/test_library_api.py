"""База знаний и выбор модели: загрузка, отказ опасному, главы, настройки без ключей наружу."""

import io
import json
import zipfile
from typing import Any

import pytest
from conftest import CHAPTER, ORIGIN, data_of, error_of, wait_for, write_json
from fastapi.testclient import TestClient
from glava.entrypoints.http.app import create_app
from glava.modules.llm.schemas import ModelChoice
from glava.modules.llm.settings import ModelStore

PDF = b"%PDF-1.7\n content"
TEXT = "Текст книги".encode()


def upload(client: TestClient, name: str = "Книга.pdf", raw: bytes = PDF, **form: Any) -> Any:
    return client.post("/api/library", files={"file": (name, io.BytesIO(raw), "application/octet-stream")}, data=form, headers=ORIGIN)


def finished(client: TestClient, source_id: str) -> Any:
    return wait_for(lambda: (s := data_of(client.get(f"/api/library/{source_id}")))["state"] != "extracting" and s)


@pytest.fixture
def source(client, root):
    """Загруженная книга с извлечённым текстом: страницы 1–4, третья — скан, четвёртая пустая."""
    found = data_of(upload(client), 201)
    finished(client, found["id"])
    folder = root / "library" / found["id"]
    states = ["text", "doubtful", "scan", "empty"]
    write_json(folder / "pages.json", {"pages": [{"page": n, "state": s, "method": "text", "chars": 9, "reasons": []} for n, s in enumerate(states, 1)]})
    (folder / "text.md").write_text("\n\n".join(f"<!-- page {n} -->\n\nТекст {n}" for n in range(1, 5)), encoding="utf-8")
    return found["id"]


def chapter(client, source_id, **over):
    return client.post(f"/api/library/{source_id}/chapters", json={"title": "Глава", "pages": [[1, 2]], "domain": "general", **over}, headers=ORIGIN)


@pytest.fixture(autouse=True)
def domain(root):
    for name in ("misconceptions.json", "difficulty.md", "styleguide.json", "physics_checklist.json"):
        write_json(root / "domain" / "general" / name, [])


# ---------- загрузка
def test_upload_starts_extraction(client, root):
    found = data_of(upload(client, vision="true"), 201)
    assert (found["name"], found["kind"], found["bytes"]) == ("Книга.pdf", "pdf", len(PDF))
    finished(client, found["id"])
    run = next(r for r in data_of(client.get("/api/runs")) if r["chapter"] == found["id"])
    argv = json.loads(run["log_tail"][0])["argv"]
    assert argv == ["extract", found["id"], "--vision"]
    assert (root / "library" / found["id"] / "original.pdf").read_bytes() == PDF


@pytest.mark.parametrize(("name", "raw"), [
    ("a.exe", b"MZ"), ("a", PDF), ("a.pdf", b"<html>"), ("a.docx", b"PK\x03\x04 broken"), ("a.png", PDF), ("a.txt", b"a\x00b"), ("a.txt", b""),
    ("a.svg", b"<svg onload=alert(1)>"), ("a.html", b"<script>"), ("key.json", b"{}"),
])
def test_wrong_file_is_refused_and_leaves_nothing(client, root, name, raw):
    error_of(upload(client, name, raw), 422)
    assert not list((root / "library").glob("*")) and not list((root / "library").glob(".*"))


@pytest.mark.parametrize("name", ["../../evil.txt", "C:\\x\\evil.txt", "/etc/evil.txt", "..\\evil.txt"])
def test_name_from_outside_never_becomes_a_path(client, root, name):
    found = data_of(upload(client, name, TEXT), 201)
    assert found["name"] == "evil.txt"
    assert sorted(p.name for p in (root / "library" / found["id"]).iterdir()) == ["original.txt", "source.json"]


def test_same_file_twice_is_a_conflict(client):
    data_of(upload(client), 201)
    error_of(upload(client, "Другое имя.pdf"), 409)


def test_real_docx_is_accepted(client):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("word/document.xml", "<x/>")
    assert data_of(upload(client, "a.docx", raw.getvalue()), 201)["kind"] == "docx"


def test_upload_from_foreign_page_is_refused(client):
    response = client.post("/api/library", files={"file": ("a.pdf", PDF)}, headers={"Origin": "http://evil.example"})
    error_of(response, 400)
    assert data_of(client.get("/api/library")) == []


def test_delete_from_foreign_page_is_refused(client, source):
    error_of(client.delete(f"/api/library/{source}", headers={"Origin": "http://evil.example"}), 400)
    assert data_of(client.get(f"/api/library/{source}"))


def test_book_may_be_bigger_than_other_requests(root, settings):
    from dataclasses import replace

    with TestClient(create_app(replace(settings, max_body_bytes=1000, max_book_bytes=5000)), base_url="http://127.0.0.1:8200") as client:
        data_of(upload(client, "a.pdf", PDF + b"x" * 2000), 201)
        error_of(upload(client, "b.pdf", PDF + b"y" * 9000), 413)
        error_of(client.post("/api/runs", json={"command": "build", "chapter": "x" * 2000}, headers=ORIGIN), 413)


# ---------- чтение
def test_list_detail_and_pages(client, source):
    listed = data_of(client.get("/api/library"))
    assert [s["id"] for s in listed] == [source] and listed[0]["state"] == "ready"
    assert listed[0]["counts"] == {"text": 1, "doubtful": 1, "scan": 1, "empty": 1}
    assert [p["state"] for p in data_of(client.get(f"/api/library/{source}"))["page_list"]] == ["text", "doubtful", "scan", "empty"]
    assert data_of(client.get(f"/api/library/{source}/pages/2")) == {"page": 2, "text": "Текст 2"}
    error_of(client.get(f"/api/library/{source}/pages/99"), 404)


def test_page_image(client, root, source):
    error_of(client.get(f"/api/library/{source}/pages/1/image"), 404)
    folder = root / "library" / source / "preview"
    folder.mkdir()
    (folder / "p00001.png").write_bytes(b"png")
    assert client.get(f"/api/library/{source}/pages/1/image").headers["content-type"] == "image/png"
    error_of(client.get(f"/api/library/{source}/pages/-1/image"), 404)


def test_original_is_shown_only_when_safe(client, source):
    pdf = client.get(f"/api/library/{source}/original")
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content == PDF
    note = data_of(upload(client, "a.md", b"<script>alert(1)</script>"), 201)["id"]
    response = client.get(f"/api/library/{note}/original")
    assert response.headers["content-type"] == "application/octet-stream" and "attachment" in response.headers["content-disposition"]


@pytest.mark.parametrize("name", ["src_000000000000", "..", "src_..", "chapters.json", "%2e%2e"])
def test_unknown_source(client, name):
    assert client.get(f"/api/library/{name}").status_code == 404
    assert client.get(f"/api/library/{name}/original").status_code == 404


# ---------- главы
def test_chapter_from_book_appears_in_the_list(client, root, source):
    created = data_of(chapter(client, source, title="  Моя глава "), 201)["id"]
    card = next(c for c in data_of(client.get("/api/chapters")) if c["id"] == created)
    assert (card["title"], card["book"], card["domain"], card["pages"]) == ("Моя глава", "Книга.pdf", "general", [1, 2])
    assert data_of(client.get(f"/api/chapters/{created}"))["parts"] == []
    assert data_of(client.post("/api/runs", json={"command": "errata", "chapter": created}, headers=ORIGIN), 201)["chapter"] == created
    entry = json.loads((root / "library" / "chapters.json").read_text(encoding="utf-8"))["chapters"][created]
    assert entry["source"] == source and entry["prefix"].isalnum()


@pytest.mark.parametrize("over", [
    {"pages": [[2, 1]]}, {"pages": [[1, 2], [2, 2]]}, {"pages": [[1, 9]]}, {"pages": [[0, 1]]}, {"pages": []}, {"pages": [[1, 100000]]},
    {"pages": [[1, 3]]}, {"pages": [[4, 4]]}, {"domain": "nowhere"}, {"domain": "../x"}, {"title": " "}, {"extra": 1},
])
def test_wrong_chapter_is_refused(client, source, over):
    error_of(chapter(client, source, **over), 422)


def test_unread_pages_do_not_silently_disappear(client, source):
    assert "3" in error_of(chapter(client, source, pages=[[1, 4]]), 422)["message"]


def test_book_with_chapters_is_protected(client, source):
    created = data_of(chapter(client, source), 201)["id"]
    error_of(client.delete(f"/api/library/{source}", headers=ORIGIN), 409)
    error_of(client.post(f"/api/library/{source}/extract", json={"vision": True}, headers=ORIGIN), 409)
    data_of(client.delete(f"/api/library/chapters/{created}", headers=ORIGIN))
    assert created not in {c["id"] for c in data_of(client.get("/api/chapters"))}
    data_of(client.delete(f"/api/library/{source}", headers=ORIGIN))
    error_of(client.get(f"/api/library/{source}"), 404)


def test_registry_chapter_cannot_be_replaced_or_removed(client, root):
    write_json(root / "library" / "chapters.json", {"chapters": {CHAPTER: {"title": "Подмена", "domain": "general", "pages": [[1, 1]]}}})
    assert data_of(client.get(f"/api/chapters/{CHAPTER}"))["title"] == "Первая глава"
    error_of(client.delete(f"/api/library/chapters/{CHAPTER}", headers=ORIGIN), 404)


def test_broken_library_does_not_hide_other_chapters(client, root):
    (root / "library").mkdir()
    (root / "library" / "chapters.json").write_text("{", encoding="utf-8")
    assert len(data_of(client.get("/api/chapters"))) == 2


def test_domains_list_general_first(client, root):
    for name in ("misconceptions.json", "difficulty.md", "styleguide.json", "physics_checklist.json"):
        write_json(root / "domain" / "astronomy" / name, [])
    assert data_of(client.get("/api/domains")) == ["general", "astronomy"]


# ---------- модель
LOCAL = {"provider": "local", "model": "qwen3:8b", "base_url": "http://127.0.0.1:11434/v1", "context": 32768}


def test_model_choice_reaches_the_build(client, root, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_PRICE_IN", "77")
    assert data_of(client.get("/api/settings/model"))["origin"] == "env"
    assert data_of(client.post("/api/settings/model", json=LOCAL, headers=ORIGIN))["origin"] == "file"
    health = data_of(client.get("/api/health"))
    assert (health["provider"], health["model"]) == ("local", "qwen3:8b")
    env = ModelStore(root, {"LLM_PROVIDER": "openai", "LLM_PRICE_IN": "77", "LLM_BASE_URL": "http://old/v1", "OPENAI_API_KEY": "k", "PATH": "p", "LLM_VERIFY_MODEL": "old"}).env()
    assert env == {"PATH": "p", "OPENAI_API_KEY": "k", "LLM_PROVIDER": "local", "LLM_MODEL": "qwen3:8b", "LLM_BASE_URL": LOCAL["base_url"], "LLM_CONTEXT": "32768"}


def test_keys_are_named_but_never_shown(root):
    view = ModelStore(root, {"OPENAI_API_KEY": "sk-secret"}).view()
    assert view.keys == {"anthropic": False, "openai": True, "local": False}
    assert "sk-secret" not in view.model_dump_json()


def test_saved_file_has_no_place_for_keys(client, root):
    error_of(client.post("/api/settings/model", json={**LOCAL, "api_key": "sk-secret"}, headers=ORIGIN), 422)
    assert not (root / "settings.local.json").exists()


@pytest.mark.parametrize("over", [
    {"provider": "other"}, {"model": None}, {"context": None}, {"base_url": "http://h:abc"}, {"model": "a b; rm"}, {"model": "--flag"}, {"base_url": "file:///etc/passwd"}, {"base_url": "http://u:p@h/v1"},
    {"base_url": "http://h/v1?key=1"}, {"base_url": "javascript:alert(1)"}, {"price_in": -1}, {"budget_usd": 0}, {"context": 10},
    {"provider": "openai"}, {"provider": "openai", "price_in": 0, "price_out": 0},
])
def test_wrong_model_choice_is_refused(client, root, over):
    error_of(client.post("/api/settings/model", json={**LOCAL, **over}, headers=ORIGIN), 422)


@pytest.mark.parametrize("raw", ['{"provider": "evil"}', "{", '{"provider": "claude_code", "extra": 1}'])
def test_broken_settings_stop_the_build_instead_of_changing_the_model(root, raw):
    (root / "settings.local.json").write_text(raw, encoding="utf-8")
    store = ModelStore(root, {"LLM_PROVIDER": "openai", "LLM_MODEL": "m"})
    assert "повреждён" in store.env()["LLM_PROVIDER"] and "повреждён" in store.view().provider


def test_key_does_not_follow_a_changed_address(root):
    env = {"LLM_API_KEY": "k", "LLM_BASE_URL": "https://mine.example/v1"}
    store = ModelStore(root, env)
    store.save(ModelChoice(provider="local", model="m", context=8192, base_url="https://other.example/v1", price_in=1, price_out=1))
    assert "LLM_API_KEY" not in store.env()
    store.save(ModelChoice(provider="local", model="m", context=8192, base_url="https://mine.example/v1", price_in=1, price_out=1))
    assert store.env()["LLM_API_KEY"] == "k"


def test_secret_inside_an_address_is_not_shown(root):
    assert ModelStore(root, {"LLM_BASE_URL": "http://u:hunter2@h/v1"}).view().base_url is None


def test_broken_registry_is_not_overwritten(client, root, source):
    (root / "library" / "chapters.json").write_text("{", encoding="utf-8")
    error_of(chapter(client, source), 500)
    assert (root / "library" / "chapters.json").read_text(encoding="utf-8") == "{"


def test_odd_page_report_does_not_break_the_list(client, root, source):
    write_json(root / "library" / source / "pages.json", {"pages": [{"page": "x"}]})
    assert data_of(client.get("/api/library"))[0]["pages"] == 0


def test_library_cannot_list_foreign_ids(client, root):
    write_json(root / "library" / "chapters.json", {"chapters": {"alpha": {"title": "x", "domain": "general", "pages": [[1, 1]]}}})
    assert "alpha" not in {c["id"] for c in data_of(client.get("/api/chapters"))}


def test_choice_without_a_model_keeps_the_default():
    assert ModelChoice(provider="claude_code").model is None


# ---------- доверие
def test_trust_reports_belong_to_one_layer(client, root):
    import hashlib

    work = root / "work" / CHAPTER
    assert data_of(client.get(f"/api/chapters/{CHAPTER}/trust")) == {"audit": None, "audit_stale": False, "verify": None, "verify_stale": False}
    digest = hashlib.sha256((work / "layer.json").read_bytes()).hexdigest()
    write_json(work / "audit.json", {"claims": 4, "layer_sha256": digest})
    write_json(work / "trust.json", {"claims": {"total": 4}, "layer_sha256": "прежний"})
    found = data_of(client.get(f"/api/chapters/{CHAPTER}/trust"))
    assert (found["audit"]["claims"], found["audit_stale"], found["verify_stale"]) == (4, False, True)
    error_of(client.get("/api/chapters/none/trust"), 404)


def test_verify_run_carries_its_flag(client):
    run = data_of(client.post("/api/runs", json={"command": "verify", "chapter": CHAPTER, "mutants": True}, headers=ORIGIN), 201)
    done = wait_for(lambda: (r := data_of(client.get(f"/api/runs/{run['id']}")))["state"] == "done" and r)
    assert json.loads(done["log_tail"][0])["argv"] == ["verify", CHAPTER, "--mutants"]
    error_of(client.post("/api/runs", json={"command": "layer", "chapter": CHAPTER, "mutants": True}, headers=ORIGIN), 422)
