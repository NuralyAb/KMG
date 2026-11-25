"""Временный корень репозитория с файлами конвейера и приложение с подставной командой."""

import json
import os
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from glava_server.app import create_app
from glava_server.config import Settings

FAKE = Path(__file__).with_name("fake_glava.py")
ORIGIN = {"Origin": "http://127.0.0.1:5190"}
BASE_URL = "http://127.0.0.1:8200"
CHAPTER = "alpha_gl1"
EMPTY_CHAPTER = "beta_gl2"
T0 = 1_760_000_000


def write_json(path: Path, data: Any, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def wait_for(check: Callable[[], Any], timeout: float = 15) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if value := check():
            return value
        time.sleep(0.02)
    raise AssertionError("не дождались условия")


def claim(number: int, text: str, quote: str, page: int, needs_scan: bool = False) -> dict[str, Any]:
    return {"id": f"alpha.n#c{number}", "text": text, "quote": quote, "page_pdf": page, "kind": "observation", "source_kind": "text",
            "by_model": False, "needs_scan": needs_scan}


def node(slug: str, order: int, claims: list[dict], **extra: Any) -> dict[str, Any]:
    return {"id": f"alpha.{slug}", "order": order, "title": f"Узел {slug}", "short_title": slug, "difficulty": {"primary": "Пр", "secondary": None},
            "threshold": False, "pages": [10], "claims": claims, "layers": {}, "needs_scan": [], **extra}


def registry(root: Path) -> dict[str, Any]:
    def entry(prefix: str, title: str, pages: list[list[int]]) -> dict[str, Any]:
        return {"file": f"{prefix}.md", "pdf": f"{prefix}.pdf", "pages": pages, "prefix": prefix, "domain": "geology", "title": title, "book": "Книга"}

    return {"root": str(root), "pdf_root": str(root),
            "chapters": {CHAPTER: entry("alpha", "Первая глава", [[10, 12], [20, 21]]), EMPTY_CHAPTER: entry("beta", "Вторая глава", [[1, 2]])}}


def fill_chapter(root: Path) -> None:
    work, out = root / "work" / CHAPTER, root / "out" / CHAPTER
    write_json(root / "domain" / "geology" / "errata" / f"{CHAPTER}.json", {"chapter": CHAPTER, "entries": [
        {"page": 10, "md": "а", "scan": "б", "kind": "recognition", "note": ""}, {"page": 11, "md": "в", "scan": "г", "kind": "suspect", "note": ""}]}, T0)
    nodes = [
        node("first", 1, [claim(1, "Чёрный сланец плотный", "сланец чёрный и плотный", 10), claim(2, "Песчаник пористый", "песчаник", 11, True)],
             needs_scan=["рис. 1"]),
        node("second", 2, [claim(3, "Глина экранирует", "глина", 12)], threshold=True),
        node("third", 3, [claim(4, "Вода тяжелее нефти", "вода", 20)]),
    ]
    write_json(work / "layer.json", {"chapter": CHAPTER, "title": "Первая глава", "nodes": nodes, "parts": [
        {"title": "Часть 1", "nodes": ["alpha.first", "alpha.second", "alpha.unbuilt"]}]}, T0 + 10)
    write_json(work / "coverage.json", {"chapter": CHAPTER, "rows": [
        {"unit_id": "p010.01", "kind": "paragraph", "page_pdf": 10, "excerpt": "а", "node_ids": ["alpha.first"], "reason": None},
        {"unit_id": "p010.02", "kind": "heading", "page_pdf": 10, "excerpt": "б", "node_ids": [], "reason": "заголовок"},
        {"unit_id": "p011.01", "kind": "figure", "page_pdf": 11, "excerpt": "в", "node_ids": ["alpha.second"], "reason": None}]}, T0 + 10)
    write_json(work / "layer_report.json", {"issues": {"alpha.first": ["раз", "два"], "alpha.second": ["три"]}, "dropped_claims": []}, T0 + 10)
    write_json(work / "routing.json", {"chapter": CHAPTER, "routes": [
        {"node_id": "alpha.first", "format": "карточки", "video_scores": {}, "why": "потому"}]}, T0 + 20)
    write_json(work / "tasks.json", {"chapter": CHAPTER, "tasks": [
        {"id": "t1", "type": "single", "step_id": "alpha.first", "claim_ids": [], "prompt": "?", "answer": "a", "explanation": ""},
        {"id": "t2", "type": "calc", "step_id": "alpha.first", "claim_ids": [], "prompt": "?", "answer": 1, "explanation": ""},
        {"id": "t3", "type": "single", "step_id": "alpha.second", "claim_ids": [], "prompt": "?", "answer": "b", "explanation": ""}]}, T0 + 30)
    write_json(work / "illustrations.json", {"chapter": CHAPTER, "illustrations": [
        {"id": "i1", "step_id": "alpha.first", "node_id": "alpha.first", "file": "pictures/first_1.svg", "caption": "", "alt": ""}]}, T0 + 25)
    for name, text in (("index.html", "<!doctype html><p>курс</p>"), ("data.js", "window.X = 1"), ("pictures/first_1.svg", "<svg/>"),
                       ("key.json", "{}"), (".hidden", "x"), ("videos/v1.mp4", "0123456789"), ("videos/v1.srt", "1")):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    os.utime(out / "index.html", (T0 + 40, T0 + 40))
    passport = {"video_id": "v1", "node_id": "alpha.first", "format": "16:9", "node_card": {"title": "Узел first"},
                "audio_check": {"duration_s": 61.5, "problems": ["тихо"]}}
    write_json(out / "videos" / "v1.passport.json", passport)
    write_json(out / "videos" / "half.passport.json", {"video_id": "half"})
    (root / "domain" / "geology" / "video").mkdir(parents=True)
    (root / "domain" / "geology" / "video" / "well_tool.py").write_text("", encoding="utf-8")


def fill_reviews(root: Path) -> None:
    remark = {"target": "C1", "category": "other", "severity": "critical", "problem": "п", "fix": "и", "page_pdf": None}
    write_json(root / "out" / "review" / "pkg_one.json", {"package_id": "pkg_one", "remarks": [remark, {**remark, "target": "C2", "severity": "minor", "page_pdf": 3, "quote": "ц"}]},
               T0)
    write_json(root / "work" / "review" / "старое_имя" / "package.json", {"package_id": "pkg_one", "chapter": CHAPTER})
    write_json(root / "work" / "review" / "старое_имя" / "key.json", {"secret": True})
    write_json(root / "out" / "review" / "pkg_two.json", {"package_id": "pkg_two", "remarks": []}, T0 + 100)
    write_json(root / "out" / "review" / "key.json", {"package_id": "key", "remarks": []})
    (root / "out" / "review" / "broken.json").write_text('{"package_id": "bro', encoding="utf-8")


METRICS = """chapter,stage,nodes,llm_tokens_in,llm_tokens_out,money_usd,person_minutes,mentor_minutes,video_seconds,manual_share
alpha_gl1,layer,3,1000,200,1.2500,0,0,0,0
alpha_gl1,tasks,3,500,100,0.2500,5,1,0,0.1
beta_gl2,review,9,10,20,0.5000,0,0,0,0
alpha_gl1,rou"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_json(tmp_path / "chapters.json", registry(tmp_path))
    (tmp_path / "metrics.csv").write_text(METRICS, encoding="utf-8")
    fill_chapter(tmp_path)
    fill_reviews(tmp_path)
    return tmp_path


@pytest.fixture
def settings(root: Path) -> Settings:
    return Settings(root=root, run_command=(sys.executable, str(FAKE)), poll_seconds=0.02)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as test_client:
        yield test_client


def data_of(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is True and body["error"] is None
    return body["data"]


def error_of(response: Any, status: int) -> dict[str, str]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"success", "data", "error", "meta"}
    assert body["success"] is False and body["data"] is None
    assert "Traceback" not in response.text
    return body["error"]
