"""routing: формат для каждого узла."""

import ast
import logging
from pathlib import Path

from glava.modules.drawing.api import load_templates
from glava.modules.format_routing.api import make_routing
from glava.modules.llm.api import Provider
from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.shared.json_files import read, save

log = logging.getLogger("glava")


def routing_context(chapter: Chapter) -> str:
    pictures = [t.SUMMARY for t in load_templates(chapter.domain / "templates").values()]
    videos = [line for file in sorted((chapter.domain / "video").glob("*.py")) if (line := template_summary(file))]
    difficulty = (chapter.domain / "difficulty.md").read_text(encoding="utf-8")
    return "\n".join(["Рисунки и интерактив:", *pictures, "", "Видео:", *videos, "", difficulty])


def template_summary(file: Path) -> str:
    """SUMMARY видеошаблона читается из текста: для рендера нужен cairo, а для маршрутизации нет."""
    for node in ast.parse(file.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SUMMARY" for t in node.targets) and isinstance(node.value, ast.Constant):
            return str(node.value.value)
    return ""


def build_routing(chapter: Chapter, provider: Provider) -> None:
    routing, replies = make_routing(provider, prompt_file("routing"), read(chapter.work / "layer.json"), routing_context(chapter))
    save(chapter.work / "routing.json", routing)
    write_metrics(chapter, "routing", len(routing["routes"]), replies)
    log.info("маршруты: %s", len(routing["routes"]))
