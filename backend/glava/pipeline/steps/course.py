"""course: сборка курса, модель не нужна."""

import logging
from pathlib import Path

from glava.modules.course.api import build_course
from glava.modules.narration.api import ready_narrations
from glava.pipeline.chapter import Chapter
from glava.shared.json_files import read, read_or
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def build_site(chapter: Chapter) -> Path:
    work = chapter.work
    layer = read(work / "layer.json")
    folder = workspace() / "out" / chapter.chapter_id
    out = build_course(layer, read_or(work / "routing.json", {"routes": []}), read_or(work / "tasks.json", {"tasks": []})["tasks"],
                       read_or(work / "illustrations.json", {"illustrations": []})["illustrations"], folder, work / "pictures",
                       simulations=work / "simulations.json", narrations=ready_narrations(read_or(work / "narration.json", {}), folder))
    log.info("курс: %s", out / "index.html")
    return out
