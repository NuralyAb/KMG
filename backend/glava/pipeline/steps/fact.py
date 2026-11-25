"""fact: что задела правка факта в слое, и разнести её по тексту шага и заданиям. Модель не нужна."""

import logging
from collections.abc import Mapping
from typing import Any

from glava.modules.errata.api import number_sources
from glava.modules.impact.api import Change, NotBuilt, leftovers, look, spread
from glava.modules.layer.api import pages_of
from glava.pipeline.chapter import Chapter, errata_of
from glava.pipeline.steps.course import build_site
from glava.pipeline.steps.lab import digest
from glava.shared.evidence import verify_layer
from glava.shared.json_files import read, read_or, save
from glava.shared.paths import workspace

log = logging.getLogger("glava")
PLACES = (("tasks", "задание"), ("pictures", "рисунок"), ("simulations", "симулятор"), ("videos", "ролик"))


def _tell(found: list[Change], report: Mapping[str, Any]) -> None:
    for change in found:
        log.info("%s\n  было:  %s\n  стало: %s", change.claim_id, change.before or "—", change.after or "—")
        if change.conflicts:
            log.warning("  расходится с цитатой на стр. %s (%s): «%s»", change.page_pdf, ", ".join(change.conflicts), change.quote)
    for step in report["steps"]:
        log.info("шаг %s «%s»", step["order"], step["title"])
    for key, name in PLACES:
        for row in report[key]:
            log.info("%s %s: %s", name, row["id"], "стоит старое число" if row["is_certain"] else "опирается на это утверждение, посмотреть")


def show_fact(chapter: Chapter) -> dict[str, Any]:
    try:
        found, report = look(workspace(), chapter.chapter_id, read(chapter.work / "layer.json"))
    except NotBuilt as error:
        raise SystemExit(f"{error}; выполните glava course") from error
    if not found and not report["fields"]:
        log.info("слой не менялся с прошлой сборки")
    _tell(found, report)
    return report


def apply_fact(chapter: Chapter, build: bool = True, accept: bool = False) -> dict[str, Any]:
    work = chapter.work
    layer = read(work / "layer.json")
    try:
        found, report = look(workspace(), chapter.chapter_id, layer)
    except NotBuilt:
        log.info("курс ещё не собирали: правку разносить не от чего")
        return {}
    _tell(found, report)
    tasks = read_or(work / "tasks.json", {"tasks": []})
    fresh, fresh_tasks, replaced, broken = spread(layer, tasks["tasks"], found)
    touched = {c.node_id for c in found}
    # проверка до записи: отклонённая правка не должна оставить следов в тексте шага
    issues = [i for i in verify_layer(fresh, pages_of(chapter.units), number_sources(errata_of(chapter))) if i.where.split(":")[0].split("#")[0] in touched]
    serious = [c.claim_id for c in found if c.is_serious]
    if serious and not accept:
        raise SystemExit(f"правка противоречит цитате ({', '.join(serious[:5])}), ничего не записано. Исправьте утверждение или цитату; если прав человек — добавьте --accept")
    if issues:
        if not accept or any(i.code != "number_not_in_source" for i in issues):
            raise SystemExit("правка не прошла проверку, ничего не записано: " + "; ".join(f"{i.where}: {i.message}" for i in issues[:8]))
        log.warning("принято человеком: %s", "; ".join(f"{i.where}: {i.message}" for i in issues[:8]))
    if replaced:
        save(work / "layer.json", fresh)
        save(work / "tasks.json", {**tasks, "tasks": fresh_tasks})
    pictures = {p["id"]: p for p in read_or(work / "illustrations.json", {"illustrations": []})["illustrations"]}
    stale = {"tasks": {t["id"]: digest(t) for t in fresh_tasks if t["id"] in broken},
             "pictures": {p["id"]: digest(pictures[p["id"]]) for p in report["pictures"] if p["is_certain"]}}
    if any(stale.values()):
        kept = read_or(work / "stale.json", {"tasks": {}, "pictures": {}})
        save(work / "stale.json", {k: {**kept[k], **stale[k]} for k in stale})
    nodes = {n["id"]: n for n in fresh["nodes"]}
    left = [row for c in found if c.node_id in nodes for row in leftovers(nodes[c.node_id], c)]
    for row in left:
        log.warning("старое число осталось, посмотрите: %s: %s", row["where"], row["text"][:160])
    report = {**report, "replaced": replaced, "leftovers": left, "tasks_hidden": broken, "pictures_marked": sorted(stale["pictures"])}
    if found or report["fields"]:
        save(work / "fact_report.json", report)
    if build:
        build_site(chapter)
    log.info("шагов %s; число заменено в %s местах; заданий скрыто до пересоставления %s; рисунков помечено %s; симуляторов посмотреть %s; роликов %s",
             len(report["steps"]), len(replaced), len(broken), len(stale["pictures"]), len(report["simulations"]), len(report["videos"]))
    return report
