"""Команды конвейера. Одна команда на главу: glava build <глава>."""

import argparse
import csv
import json
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glava.course.build import build_course
from glava.llm import Ledger, Provider, Reply, cached
from glava.llm.providers import provider_from_env
from glava.stages.layer import coverage_rows, drop_unsupported, load_schema, make_node, make_plan, pages_of
from glava.stages.routing import make_routing
from glava.stages.tasks import chapter_task_issues, groups, make_tasks, number_tasks
from glava.units import Unit, parse_units, read_pages

ROOT = Path(__file__).resolve().parents[2]
PARALLEL = 4
BUDGET_USD = 12.0
METRIC_FIELDS = ("chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes", "mentor_minutes",
                 "video_seconds", "manual_share")
log = logging.getLogger("glava")


@dataclass(frozen=True)
class Chapter:
    chapter_id: str
    prefix: str
    title: str
    book: str
    domain: Path
    units: tuple[Unit, ...]
    source: str

    @property
    def work(self) -> Path:
        return ROOT / "work" / self.chapter_id


def load_chapter(chapter_id: str) -> Chapter:
    registry = json.loads((ROOT / "chapters.json").read_text(encoding="utf-8"))
    info = registry["chapters"][chapter_id]
    md = (Path(registry["root"]) / info["file"]).read_text(encoding="utf-8")
    units = parse_units(read_pages(md, [tuple(r) for r in info["pages"]]))
    return Chapter(chapter_id, info["prefix"], info["title"], info["book"], ROOT / "domain" / info["domain"], tuple(units), info["file"])


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_file(name: str) -> str:
    return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def context_of(chapter: Chapter) -> str:
    misconceptions = read(chapter.domain / "misconceptions.json")
    listed = "\n".join(f"{m['id']}: {m['text']}" for m in misconceptions)
    difficulty = (chapter.domain / "difficulty.md").read_text(encoding="utf-8")
    return f"# Глава\n{chapter.title}. {chapter.book}\n\n# Заблуждения новичков\n{listed}\n\n# {difficulty}"


def write_metrics(chapter: Chapter, stage: str, nodes: int, replies: Sequence[Reply]) -> None:
    path = ROOT / "metrics.csv"
    is_new = not path.exists()
    row = [chapter.chapter_id, stage, nodes, sum(r.input_tokens for r in replies), sum(r.output_tokens for r in replies),
           f"{sum(r.cost_usd for r in replies):.4f}", 0, 0, 0, 0]
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        if is_new:
            writer.writerow(METRIC_FIELDS)
        writer.writerow(row)


def build_layer(chapter: Chapter, provider: Provider, limit: int | None = None) -> dict[str, Any]:
    context = context_of(chapter)
    plan, plan_replies = make_plan(provider, prompt_file("plan"), context, chapter.units)
    save(chapter.work / "plan.json", plan)
    Ledger(BUDGET_USD).add("plan", *plan_replies).check()
    count = min(limit or len(plan["nodes"]), len(plan["nodes"]))
    log.info("план: узлов %s, собираю %s", len(plan["nodes"]), count)

    def one(index: int) -> tuple[dict, list[str], list[Reply]]:
        return make_node(provider, prompt_file("node"), context, plan, index, chapter.units, chapter.prefix)

    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(one, range(count)))
    pages = pages_of(chapter.units)
    cleaned = [drop_unsupported(node, pages) for node, _, _ in results]
    layer = {
        "chapter": chapter.chapter_id, "source": chapter.source, "pdf_pages": sorted({str(u.page_pdf) for u in chapter.units}),
        "generated_by": f"{provider.name}/{provider.model}", "title": chapter.title, "book": chapter.book,
        "parts": [{"title": p["title"], "nodes": [f"{chapter.prefix}.{s}" for s in p["slugs"]]} for p in plan["parts"]],
        "nodes": [node for node, _ in cleaned],
    }
    report = {"issues": {node["id"]: issues for node, issues, _ in results if issues},
              "dropped_claims": [cid for _, dropped in cleaned for cid in dropped],
              "nodes": len(layer["nodes"]), "claims": sum(len(n["claims"]) for n in layer["nodes"])}
    save(chapter.work / "layer.json", layer)
    save(chapter.work / "coverage.json", {"chapter": chapter.chapter_id, "rows": coverage_rows(plan, chapter.units, chapter.prefix)})
    save(chapter.work / "layer_report.json", report)
    replies = [*plan_replies, *(r for _, _, rs in results for r in rs)]
    write_metrics(chapter, "layer", len(layer["nodes"]), replies)
    log.info("слой: узлов %s, утверждений %s, отброшено %s, замечания в узлах: %s, $%.2f", report["nodes"], report["claims"],
             len(report["dropped_claims"]), len(report["issues"]), sum(r.cost_usd for r in replies))
    return layer


def build_routing(chapter: Chapter, provider: Provider) -> None:
    templates = "
".join(p.stem for p in sorted((chapter.domain / "templates").glob("*"))) or "шаблонов пока нет"
    routing, replies = make_routing(provider, prompt_file("routing"), read(chapter.work / "layer.json"), templates)
    save(chapter.work / "routing.json", routing)
    write_metrics(chapter, "routing", len(routing["routes"]), replies)
    log.info("маршруты: %s", len(routing["routes"]))


def build_tasks(chapter: Chapter, provider: Provider) -> None:
    nodes = read(chapter.work / "layer.json")["nodes"]
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda g: make_tasks(provider, prompt_file("tasks"), g), groups(nodes)))
    tasks = number_tasks(t for found, _ in results for t in found)
    save(chapter.work / "tasks.json", {"chapter": chapter.chapter_id, "tasks": tasks})
    write_metrics(chapter, "tasks", len(nodes), [r for _, rs in results for r in rs])
    log.info("задания: %s; замечания: %s", len(tasks), chapter_task_issues(tasks) or "нет")


def read_or(path: Path, default: Any) -> Any:
    return read(path) if path.exists() else default


def build_site(chapter: Chapter) -> Path:
    work = chapter.work
    out = build_course(read(work / "layer.json"), read_or(work / "routing.json", {"routes": []}), read_or(work / "tasks.json", {"tasks": []})["tasks"],
                       read_or(work / "illustrations.json", {"illustrations": []})["illustrations"], ROOT / "out" / chapter.chapter_id, work / "pictures")
    log.info("курс: %s", out / "index.html")
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="glava", description="Глава книги -> учебный слой -> демо-курс")
    parser.add_argument("command", choices=["build", "layer", "routing", "tasks", "course", "units"])
    parser.add_argument("chapter")
    parser.add_argument("--limit", type=int, default=None, help="собрать только первые N узлов")
    args = parser.parse_args()
    chapter = load_chapter(args.chapter)
    load_schema("node")
    if args.command == "units":
        for unit in chapter.units:
            log.info("%s %s %s", unit.unit_id, unit.kind, unit.excerpt)
        return
    if args.command == "course":
        build_site(chapter)
        return
    provider = cached(provider_from_env(), ROOT / ".cache")
    if args.command in ("build", "layer"):
        build_layer(chapter, provider, args.limit)
    if args.command in ("build", "routing"):
        build_routing(chapter, provider)
    if args.command in ("build", "tasks"):
        build_tasks(chapter, provider)
    if args.command == "build":
        build_site(chapter)


if __name__ == "__main__":
    main()
