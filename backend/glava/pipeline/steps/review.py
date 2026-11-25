"""review: проверка чужого пакета."""

import logging
from pathlib import Path

from glava.modules.layer.api import pages_of
from glava.modules.library.api import CHAPTER_PREFIX, LibraryError
from glava.modules.llm.api import Provider
from glava.modules.review.api import load_package, review_package
from glava.modules.review.api import workspace as review_workspace
from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.shared.json_files import save
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def build_review(chapter: Chapter, source: Path, provider: Provider) -> Path:
    """Проверка чужого пакета; ответ — out/review/<пакет>.json."""
    if chapter.chapter_id.startswith(CHAPTER_PREFIX):
        raise LibraryError("проверка пакета по главе базы знаний не поддерживается: ответ с цитатами книги попал бы в git")
    package = load_package(source)
    folder = review_workspace(source, workspace() / "work" / "review", package["package_id"])
    prompts = {role: prompt_file(f"review_{role}") for role in ("find", "physics", "judge")}
    checklist = (chapter.domain / "physics_checklist.json").read_text(encoding="utf-8")
    answer, replies = review_package(package, pages_of(chapter.units), provider, prompts, checklist, folder)
    target = workspace() / "out" / "review" / f"{package['package_id']}.json"
    save(target, answer)
    write_metrics(chapter, "review", len(package["items"]) + len(package["frames"]), replies)
    log.info("замечаний %s, $%.2f, ответ: %s", len(answer["remarks"]), sum(r.cost_usd for r in replies), target)
    return target
