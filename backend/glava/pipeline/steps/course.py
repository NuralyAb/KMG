"""course: сборка курса, модель не нужна."""

import logging
from pathlib import Path
from typing import Any

from glava.modules.course.api import build_course
from glava.modules.narration.api import ready_narrations
from glava.pipeline.chapter import Chapter
from glava.shared.json_files import read, read_or
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def course_videos(chapter_id: str) -> dict[str, list[dict[str, Any]]]:
    """Готовые ролики по шагам: ролик без mp4 или субтитров в курс не попадает."""
    folder = workspace() / "out" / chapter_id / "videos"
    found: dict[str, list[dict[str, Any]]] = {}
    for file in sorted(folder.glob("*.passport.json")):
        name, passport = file.name.removesuffix(".passport.json"), read(file)
        if not (folder / f"{name}.mp4").exists() or not (folder / f"{name}.srt").exists():
            continue
        labels = list(dict.fromkeys(f["label"] for f in passport["frames"]))
        video = {"title": passport["node_card"].get("short_title") or passport["node_card"]["title"], "src": f"videos/{name}.mp4", "subtitles": f"videos/{name}.srt",
                 "format": passport["format"], "label": ", ".join(labels)}
        found = {**found, passport["node_id"]: [*found.get(passport["node_id"], []), video]}
    return found


def build_site(chapter: Chapter) -> Path:
    work = chapter.work
    layer = read(work / "layer.json")
    folder = workspace() / "out" / chapter.chapter_id
    out = build_course(layer, read_or(work / "routing.json", {"routes": []}), read_or(work / "tasks.json", {"tasks": []})["tasks"],
                       read_or(work / "illustrations.json", {"illustrations": []})["illustrations"], folder, work / "pictures",
                       extras={step: {"videos": videos} for step, videos in course_videos(chapter.chapter_id).items() if step in {n["id"] for n in layer["nodes"]}},
                       simulations=work / "simulations.json", narrations=ready_narrations(read_or(work / "narration.json", {}), folder))
    log.info("курс: %s", out / "index.html")
    return out
