"""Паспорт переноса и лаборатория рядом с курсом."""

import json
from pathlib import Path
from typing import Any

from glava.modules.lab.api import publish_lab
from glava.modules.transfer.api import make_passport
from glava.pipeline.steps.lab import digest, fresh_pictures, fresh_tasks
from glava.shared.json_files import save


def layer(**extra: Any) -> dict[str, Any]:
    claim = {"id": "a.n#c1", "text": "т", "quote": "ц", "page_pdf": 3, "kind": "observation", "needs_scan": True}
    node = {"id": "a.n", "order": 1, "short_title": "Узел", "claims": [claim], "difficulty": {"primary": "Ф", "secondary": None}, "links": [{"type": "prerequisite", "target": "a.m"}]}
    return {"chapter": "a", "title": "Г", "book": "К", "nodes": [{**node, **extra}]}


def passport(edits: list[dict[str, str]], route: dict[str, Any] | None = None, audit: dict[str, Any] | None = None) -> dict[str, Any]:
    routes = [{"node_id": "a.n", "format": "интерактив", "video_scores": {"time": 2}, "template": "нет такого", **(route or {})}]
    metrics = [{"chapter": "a", "stage": "layer", "money_usd": "1.5"}, {"chapter": "b", "stage": "layer", "money_usd": "9"}]
    return make_passport(layer(), [{"node_ids": [], "reason": None}], routes, [], [], [], 0, audit, metrics, edits, ["plot"])


def state(report: dict[str, Any], key: str) -> str:
    return next(c["state"] for c in report["checks"] if c["id"] == key)


def test_gaps_are_named_and_unmeasured_is_not_zero() -> None:
    report = passport([])
    assert state(report, "coverage") == "bad" and state(report, "tasks") == "bad" and state(report, "scan") == "warn"
    assert state(report, "audit") == "unknown" and state(report, "labour") == "unknown"
    assert report["scan_pages"] == [3]


def test_edit_without_minutes_is_a_fault() -> None:
    report = passport([{"chapter": "a", "person_minutes": ""}, {"chapter": "a", "person_minutes": "4"}])
    assert state(report, "labour") == "bad" and report["labour"]["unmeasured"] == 1 and report["labour"]["minutes"] == 4


def test_labour_within_the_limit_is_good() -> None:
    assert state(passport([{"chapter": "a", "person_minutes": "12.5"}, {"chapter": "b", "person_minutes": "500"}]), "labour") == "good"


def test_money_is_counted_for_this_chapter_only() -> None:
    assert passport([])["cost"] == {"total_usd": 1.5, "per_node_usd": 1.5, "stages": [{"stage": "layer", "usd": 1.5}]}


def test_template_states() -> None:
    assert passport([])["templates"][0]["state"] == "new"
    assert passport([], {"template": "plot"})["templates"][0]["state"] == "template"
    assert passport([], {"format": "карточки"})["templates"] == []


def test_stale_task_is_hidden_until_it_is_rewritten(tmp_path: Path) -> None:
    task, picture = {"id": "t", "prompt": "1"}, {"id": "p", "caption": "Кривая."}
    save(tmp_path / "tasks.json", {"tasks": [task]})
    save(tmp_path / "illustrations.json", {"illustrations": [picture]})
    assert fresh_tasks(tmp_path) == [task] and fresh_pictures(tmp_path) == [picture]
    save(tmp_path / "stale.json", {"tasks": {"t": digest(task)}, "pictures": {"p": digest(picture)}})
    assert fresh_tasks(tmp_path) == []
    assert "до правки факта" in fresh_pictures(tmp_path)[0]["caption"]
    save(tmp_path / "tasks.json", {"tasks": [{**task, "prompt": "2"}]})
    assert len(fresh_tasks(tmp_path)) == 1


def test_lab_is_put_next_to_the_course_once(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body><p></p></body></html>", encoding="utf-8")
    for _ in range(2):
        publish_lab(tmp_path, {"misconceptions": {"m": "</script>"}, "practice": None, "passport": {}})
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert page.count("lab/diagnosis.js") == 1 and page.count("lab/data.js") == 1
    data = (tmp_path / "lab" / "data.js").read_text(encoding="utf-8")
    assert "</script>" not in data
    assert json.loads(data.removeprefix("window.LAB=").rstrip().removesuffix(";"))["misconceptions"]["m"] == "</script>"
    assert (tmp_path / "lab.html").exists() and not (tmp_path / "lab" / "lab.html").exists()
    for name in ("lab.css", "lab.js", "well.js", "core.js"):
        assert (tmp_path / "lab" / name).exists()
    assert not any(mark in p.read_text(encoding="utf-8") for p in (tmp_path / "lab").glob("*.js") for mark in ("http://", "https://", "fetch("))
