"""course: сборка курса, модель не нужна."""

import logging
from pathlib import Path

from glava.modules.course.api import build_course
from glava.pipeline.chapter import Chapter
from glava.shared.json_files import read, read_or
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def build_site(chapter: Chapter) -> Path:
    work = chapter.work
    layer = read(work / "layer.json")
    out = build_course(layer, read_or(work / "routing.json", {"routes": []}), read_or(work / "tasks.json", {"tasks": []})["tasks"],
                       read_or(work / "illustrations.json", {"illustrations": []})["illustrations"], workspace() / "out" / chapter.chapter_id, work / "pictures",
                       simulations=work / "simulations.json")
    log.info("курс: %s", out / "index.html")
    return out
