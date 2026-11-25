"""videos: ролики главы по маршрутизации. Узел берётся из маршрутов, шаблон подбирает код; ролик, который не вышел, попадает в отчёт и главу не останавливает."""

import importlib.util
import json
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from glava.modules.llm.api import Provider
from glava.pipeline.chapter import Chapter
from glava.pipeline.steps.reports import (
    VIDEO_FORMATS,
    VideoTemplate,
    template_for,
    video_templates,
)
from glava.pipeline.steps.video import build_video, film_spec, specs_folder
from glava.shared.json_files import read, save

log = logging.getLogger("glava")
KINDS = {"шортс": "short", "длинное видео": "wide"}
DEFAULT_LIMIT = 2


def wanted(layer: Mapping[str, Any], routes: Sequence[Mapping[str, Any]], templates: Sequence[VideoTemplate]) -> list[dict[str, Any]]:
    """Видеоузлы от самых видеоёмких; узел без шаблона остаётся в списке с template: null."""
    nodes = {n["id"]: n for n in layer["nodes"]}
    chosen = [r for r in routes if r["format"] in VIDEO_FORMATS and r["node_id"] in nodes]
    ranked = sorted(chosen, key=lambda r: (-sum(r["video_scores"].values()), nodes[r["node_id"]]["order"]))
    rows: list[dict[str, Any]] = []
    for route in ranked:
        template, why = template_for(nodes[route["node_id"]], route, templates)
        rows = [*rows, {"node_id": route["node_id"], "format": KINDS[route["format"]], "template": template.name if template else None, "why": why}]
    return rows


def limit_from_env(env: Mapping[str, str]) -> int:
    value = env.get("GLAVA_VIDEOS", str(DEFAULT_LIMIT))
    if not value.isdigit():
        raise SystemExit("GLAVA_VIDEOS: сколько роликов снимать за сборку, целое число от 0")
    return int(value)


def _one(chapter: Chapter, open_provider: Callable[[], Provider], row: Mapping[str, Any], voice: str | None) -> str:
    """Готовая спецификация используется снова: повтор сборки за неё не платит."""
    ready = specs_folder(chapter) / f"{row['node_id'].replace('.', '_')}_{row['format']}.json"
    if ready.exists() and json.loads(ready.read_text(encoding="utf-8"))["template"] == row["template"]:
        film_spec(chapter, ready, voice)
        return "снят по готовой спецификации"
    build_video(chapter, open_provider, row["node_id"], row["format"], row["template"], voice)
    return "снят"


def build_videos(chapter: Chapter, open_provider: Callable[[], Provider], limit: int | None = None, voice: str | None = None) -> list[dict[str, Any]]:
    rows = wanted(read(chapter.work / "layer.json"), read(chapter.work / "routing.json")["routes"], video_templates(chapter.domain))
    count = limit_from_env(os.environ) if limit is None else limit
    able = importlib.util.find_spec("cairo") is not None
    report: list[dict[str, Any]] = []
    for row in rows:
        left = count - sum(r["result"].startswith("снят") for r in report)
        if row["template"] is None:
            result = "нужен новый шаблон"
        elif left <= 0:
            result = "сверх предела GLAVA_VIDEOS"
        elif not able:
            result = "нет пакетов группы video"
        else:
            try:
                result = _one(chapter, open_provider, row, voice)
            except (SystemExit, RuntimeError, ValueError, OSError) as error:
                result = f"не снят: {str(error)[:300]}"
        report = [*report, {**row, "result": result}]
        log.info("ролик %s [%s, %s]: %s", row["node_id"], row["format"], row["template"], result)
    save(chapter.work / "video_report.json", {"chapter": chapter.chapter_id, "rows": report})
    return report
