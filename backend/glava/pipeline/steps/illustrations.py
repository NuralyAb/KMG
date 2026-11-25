"""illustrations: рисунки SVG."""

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from glava.modules.drawing.api import load_style, load_templates
from glava.modules.illustrations.api import make_illustrations, records
from glava.modules.llm.api import Provider, Reply
from glava.modules.tasks.api import groups
from glava.pipeline.chapter import Chapter, errata_of, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import read, save

log = logging.getLogger("glava")


def build_illustrations(chapter: Chapter, provider: Provider) -> None:
    nodes = read(chapter.work / "layer.json")["nodes"]
    templates, style = load_templates(chapter.domain / "templates"), load_style(chapter.domain)
    prompt = prompt_file("illustrations")
    errata = errata_of(chapter)

    def scenes_for(part: Sequence[dict]) -> tuple[list[dict], list[Reply]]:
        return make_illustrations(provider, prompt, part, templates, style, errata)

    with ThreadPoolExecutor(PARALLEL) as pool:
        first = list(pool.map(scenes_for, groups(nodes)))
        drawn = {s["node_id"] for found, _ in first for s in found}
        # узлы без рисунка спрашиваются ещё раз по одному
        second = list(pool.map(scenes_for, [[n] for n in nodes if n["id"] not in drawn]))
    results = [*first, *second]
    found = records([s for scenes, _ in results for s in scenes], nodes, templates, style, chapter.work / "pictures")
    save(chapter.work / "illustrations.json", {"chapter": chapter.chapter_id, "illustrations": found})
    write_metrics(chapter, "illustrations", len(nodes), [r for _, rs in results for r in rs])
    without = sorted({n["id"] for n in nodes} - {r["step_id"] for r in found})
    log.info("иллюстрации: %s; шаги без рисунка: %s", len(found), without or "нет")
