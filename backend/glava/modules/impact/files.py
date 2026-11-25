"""Живой факт на файлах главы: след прошлой сборки и всё, что опирается на утверждения."""

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from glava.modules.impact.diff import Change, changes, snapshot_from_course
from glava.modules.impact.reach import reach
from glava.shared.json_files import read, read_or

TAG = re.compile(r"<[^>]+>")


class NotBuilt(Exception):
    """Курс ещё не собирали: сравнивать не с чем."""


def baseline(root: Path, chapter_id: str) -> dict[str, Any]:
    """След прошлой сборки; у курса, собранного раньше этой команды, утверждения берутся из него самого."""
    built = root / "work" / chapter_id / "built.json"
    if built.exists():
        return read(built)
    data = root / "out" / chapter_id / "data.js"
    text = data.read_text(encoding="utf-8") if data.exists() else ""
    if not text.startswith("window.COURSE="):
        raise NotBuilt("курс ещё не собирали: сравнивать не с чем")
    return snapshot_from_course(json.loads(text.removeprefix("window.COURSE=").rstrip().removesuffix(";")))


def drawn_text(file: Path) -> str:
    return TAG.sub(" ", file.read_text(encoding="utf-8")) if file.suffix == ".svg" and file.exists() else ""


def reach_of(root: Path, chapter_id: str, layer: Mapping[str, Any], found: Sequence[Change], fields: Mapping[str, Sequence[str]]) -> dict[str, list[dict[str, Any]]]:
    work = root / "work" / chapter_id
    pictures = read_or(work / "illustrations.json", {"illustrations": []})["illustrations"]
    passports = {p.name.removesuffix(".passport.json"): read(p) for p in sorted((root / "out" / chapter_id / "videos").glob("*.passport.json"))}
    return reach(layer, found, fields, read_or(work / "tasks.json", {"tasks": []})["tasks"], pictures,
                 {p["id"]: drawn_text(work / p["file"]) for p in pictures if p.get("file")}, read_or(work / "simulations.json", {"steps": {}})["steps"], passports)


def look(root: Path, chapter_id: str, layer: Mapping[str, Any]) -> tuple[list[Change], dict[str, Any]]:
    """Что изменилось с прошлой сборки и куда дошло. Ничего не пишет."""
    found, fields = changes(baseline(root, chapter_id), layer)
    return found, {"chapter": chapter_id, "changes": [c.to_json() for c in found], "fields": fields, **reach_of(root, chapter_id, layer, found, fields)}
