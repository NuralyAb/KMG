"""passport: паспорт переноса по главе. Модель не нужна."""

import csv
import logging
from pathlib import Path
from typing import Any

from glava.modules.transfer.api import make_passport
from glava.pipeline.chapter import Chapter
from glava.shared.json_files import read, read_or, save
from glava.shared.paths import REPOSITORY, workspace

log = logging.getLogger("glava")
MARK = {"good": "+", "warn": "!", "bad": "X", "unknown": "?"}
# шаблоны рисунков, которые есть в самом движке
BUILT_IN = ("bars", "compare", "flow", "formula", "plot")


def rows_of(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def passport_of(chapter_id: str, domain: Path, layer: dict[str, Any]) -> dict[str, Any]:
    work = workspace() / "work" / chapter_id
    templates = {*BUILT_IN, *(p.stem for folder in (domain, domain.parent / "general") for kind in ("templates", "video") for p in (folder / kind).glob("*.py"))}
    videos = list((workspace() / "out" / chapter_id / "videos").glob("*.passport.json"))
    return make_passport(
        layer, read_or(work / "coverage.json", {"rows": []})["rows"], read_or(work / "routing.json", {"routes": []})["routes"],
        read_or(work / "tasks.json", {"tasks": []})["tasks"], read_or(work / "illustrations.json", {"illustrations": []})["illustrations"],
        read_or(work / "simulations.json", {"steps": {}})["steps"], len(videos), read_or(work / "audit.json", None),
        rows_of(workspace() / "metrics.csv"), rows_of(REPOSITORY / "manual_edits.csv"), templates)


def build_passport(chapter: Chapter) -> dict[str, Any]:
    passport = passport_of(chapter.chapter_id, chapter.domain, read(chapter.work / "layer.json"))
    save(chapter.work / "passport.json", passport)
    for row in passport["checks"]:
        log.info("[%s] %s: %s (нужно: %s)%s", MARK[row["state"]], row["title"], row["value"], row["target"], f" — {row['note']}" if row["note"] else "")
    for row in passport["templates"]:
        if row["state"] == "new":
            log.info("    нужен новый шаблон: шаг %s «%s», трудность %s", row["order"], row["title"], row["difficulty"]["primary"])
    log.info("расход $%.2f, на узел $%s", passport["cost"]["total_usd"], passport["cost"]["per_node_usd"])
    return passport
