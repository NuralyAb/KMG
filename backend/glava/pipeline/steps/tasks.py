"""tasks: задания пяти типов."""

import logging
from concurrent.futures import ThreadPoolExecutor

from glava.modules.llm.api import Provider
from glava.modules.tasks.api import (
    chapter_task_issues,
    groups,
    make_tasks,
    number_tasks,
)
from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import read, save

log = logging.getLogger("glava")


def build_tasks(chapter: Chapter, provider: Provider) -> None:
    nodes = read(chapter.work / "layer.json")["nodes"]
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda g: make_tasks(provider, prompt_file("tasks"), g), groups(nodes)))
    tasks = number_tasks(t for found, _ in results for t in found)
    save(chapter.work / "tasks.json", {"chapter": chapter.chapter_id, "tasks": tasks})
    write_metrics(chapter, "tasks", len(nodes), [r for _, rs in results for r in rs])
    log.info("задания: %s; замечания: %s", len(tasks), chapter_task_issues(tasks) or "нет")
