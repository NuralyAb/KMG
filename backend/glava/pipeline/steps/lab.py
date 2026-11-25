"""Лаборатория курса и след сборки: что не устарело после правки факта и что сказать ученику. Модель не нужна."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from glava.modules.impact.api import snapshot
from glava.modules.lab.api import publish_lab
from glava.pipeline.chapter import Chapter
from glava.pipeline.steps.passport import passport_of
from glava.shared.json_files import read, read_or, save

STALE_NOTE = " Рисунок построен до правки факта, число в нём прежнее."


def digest(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _stale(work: Path, kind: str) -> dict[str, str]:
    return read_or(work / "stale.json", {}).get(kind, {})


def fresh_tasks(work: Path) -> list[dict[str, Any]]:
    """Задание, которое правка факта сделала неверным, в курс не идёт, пока его не составят заново."""
    marks = _stale(work, "tasks")
    return [t for t in read_or(work / "tasks.json", {"tasks": []})["tasks"] if marks.get(t["id"]) != digest(t)]


def fresh_pictures(work: Path) -> list[dict[str, Any]]:
    """Рисунок со старым числом остаётся, но говорит об этом в подписи."""
    marks = _stale(work, "pictures")
    rows = read_or(work / "illustrations.json", {"illustrations": []})["illustrations"]
    return [{**p, "caption": (p.get("caption") or "") + STALE_NOTE} if marks.get(p["id"]) == digest(p) else p for p in rows]


def practice_of(chapter: Chapter) -> dict[str, Any] | None:
    """Практика на открытых данных лежит в доменном пакете и сама говорит, каким главам подходит."""
    for file in sorted((chapter.domain / "practice").glob("*.json")):
        data = read(file)
        if chapter.chapter_id in data.get("chapters", ()) and data.get("wells"):
            return data
    return None


def put_lab(chapter: Chapter, layer: Mapping[str, Any], out: Path) -> None:
    save(chapter.work / "built.json", snapshot(layer))
    misconceptions = read_or(chapter.domain / "misconceptions.json", [])
    publish_lab(out, {"misconceptions": {m["id"]: m["text"] for m in misconceptions}, "practice": practice_of(chapter),
                      "passport": passport_of(chapter.chapter_id, chapter.domain, dict(layer))})
