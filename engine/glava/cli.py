"""Команды конвейера. Одна команда на главу: glava build <глава>."""

import argparse
import csv
import json
import logging
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glava.course.build import build_course
from glava.llm import Provider, Reply, cached, metered
from glava.llm.providers import provider_from_env
from glava.review.engine import load_package, review_package, workspace
from glava.scenes import load_style, load_templates
from glava.stages.enrich import apply, make_enrichment
from glava.stages.errata import make_errata, render_page
from glava.stages.illustrations import make_illustrations, records
from glava.stages.layer import coverage_rows, drop_unsupported, load_schema, make_node, make_plan, pages_of, plan_issues
from glava.stages.routing import make_routing
from glava.stages.tasks import chapter_task_issues, groups, make_tasks, number_tasks
from glava.units import Unit, parse_units, read_pages

ROOT = Path(__file__).resolve().parents[2]
PARALLEL = 4
BUDGET_USD = float(os.environ.get("GLAVA_BUDGET_USD", "25"))
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
    pdf: Path | None = None

    @property
    def work(self) -> Path:
        return ROOT / "work" / self.chapter_id

    @property
    def errata_file(self) -> Path:
        return self.domain / "errata" / f"{self.chapter_id}.json"


def load_chapter(chapter_id: str) -> Chapter:
    registry = json.loads((ROOT / "chapters.json").read_text(encoding="utf-8"))
    info = registry["chapters"][chapter_id]
    md = (ROOT / os.environ.get("GLAVA_BOOKS", registry["root"]) / info["file"]).read_text(encoding="utf-8")
    units = parse_units(read_pages(md, [tuple(r) for r in info["pages"]]))
    return Chapter(chapter_id, info["prefix"], info["title"], info["book"], ROOT / "domain" / info["domain"], tuple(units), info["file"],
                   ROOT / os.environ.get("GLAVA_PDFS", registry["pdf_root"]) / info["pdf"] if info.get("pdf") else None)


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_file(name: str) -> str:
    return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def context_of(chapter: Chapter) -> str:
    misconceptions = read(chapter.domain / "misconceptions.json")
    listed = "\n".join(f"{m['id']}: {m['text']}" for m in misconceptions)
    difficulty = (chapter.domain / "difficulty.md").read_text(encoding="utf-8")
    return f"# Глава\n{chapter.title}. {chapter.book}\n\n# Заблуждения новичков\n{listed}\n\n# {difficulty}"


def write_metrics(chapter: Chapter, stage: str, nodes: int, replies: Sequence[Reply], video_seconds: float = 0) -> None:
    path = ROOT / "metrics.csv"
    is_new = not path.exists()
    row = [chapter.chapter_id, stage, nodes, sum(r.input_tokens for r in replies), sum(r.output_tokens for r in replies),
           f"{sum(r.cost_usd for r in replies):.4f}", 0, 0, video_seconds, 0]
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        if is_new:
            writer.writerow(METRIC_FIELDS)
        writer.writerow(row)


def build_errata(chapter: Chapter, provider: Provider) -> None:
    """Сверка md со сканом. Без PDF этап пропускается: лист опечаток остаётся пустым."""
    if chapter.pdf is None or not chapter.pdf.exists():
        log.info("PDF главы не указан, лист опечаток пропущен")
        return
    pages, prompt = pages_of(chapter.units), prompt_file("errata")
    images = {n: render_page(chapter.pdf, n, chapter.work / "scans") for n in pages}
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda n: make_errata(provider, prompt, n, pages[n], images[n]), pages))
    entries = [e for found, _ in results for e in found]
    save(chapter.errata_file, {"chapter": chapter.chapter_id, "entries": entries})
    write_metrics(chapter, "errata", len(pages), [r for _, rs in results for r in rs])
    log.info("лист опечаток: %s записей, из них подозрительных мест издания: %s", len(entries), sum(e["kind"] == "suspect" for e in entries))


def enrich_nodes(chapter: Chapter, provider: Provider, nodes: Sequence[dict], errata: Sequence[dict]) -> tuple[list[dict], list[Reply], list[str]]:
    """Блоки страницы шага. Узел, который модель не дополнила, остаётся как был и попадает в отчёт."""
    note = chapter.domain / "now_practice.md"
    prompt, now = prompt_file("enrich"), note.read_text(encoding="utf-8") if note.exists() else ""

    def rows_for(part: Sequence[dict]) -> tuple[dict[str, dict], list[Reply]]:
        return make_enrichment(provider, prompt, part, now, errata)

    with ThreadPoolExecutor(PARALLEL) as pool:
        first = list(pool.map(rows_for, groups(nodes)))
        done = {k for found, _ in first for k in found}
        second = list(pool.map(rows_for, [[n] for n in nodes if n["id"] not in done]))
    rows = {k: v for found, _ in (*first, *second) for k, v in found.items()}
    units = chapter.units
    return [apply(n, rows.get(n["id"]), units, errata) for n in nodes], [r for _, rs in (*first, *second) for r in rs], [n["id"] for n in nodes if n["id"] not in rows]


def build_layer(chapter: Chapter, provider: Provider, limit: int | None = None) -> dict[str, Any]:
    context = context_of(chapter)
    errata = read_or(chapter.errata_file, {"entries": []})["entries"]
    plan, plan_replies = make_plan(provider, prompt_file("plan"), context, chapter.units)
    save(chapter.work / "plan.json", plan)
    unfixed = plan_issues(plan, chapter.units)
    if unfixed:
        raise SystemExit("план главы не прошёл проверку: " + "; ".join(unfixed[:5]))
    count = min(limit or len(plan["nodes"]), len(plan["nodes"]))
    log.info("план: узлов %s, собираю %s", len(plan["nodes"]), count)

    def one(index: int) -> tuple[dict, list[str], list[Reply]]:
        return make_node(provider, prompt_file("node"), context, plan, index, chapter.units, chapter.prefix, errata)

    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(one, range(count)))
    pages = pages_of(chapter.units)
    cleaned = [drop_unsupported(node, pages, errata) for node, _, _ in results]
    nodes, enrich_replies, plain = enrich_nodes(chapter, provider, [node for node, _ in cleaned], errata)
    layer = {
        "chapter": chapter.chapter_id, "source": chapter.source, "pdf_pages": sorted({str(u.page_pdf) for u in chapter.units}),
        "generated_by": f"{provider.name}/{provider.model}", "title": chapter.title, "book": chapter.book,
        "parts": [{"title": p["title"], "nodes": [f"{chapter.prefix}.{s}" for s in p["slugs"]]} for p in plan["parts"]],
        "nodes": nodes,
    }
    report = {"issues": {node["id"]: issues for node, issues, _ in results if issues},
              "dropped_claims": [cid for _, dropped in cleaned for cid in dropped],
              "not_enriched": plain, "nodes": len(layer["nodes"]), "claims": sum(len(n["claims"]) for n in layer["nodes"])}
    save(chapter.work / "layer.json", layer)
    save(chapter.work / "coverage.json", {"chapter": chapter.chapter_id, "rows": coverage_rows(plan, chapter.units, chapter.prefix)})
    save(chapter.work / "layer_report.json", report)
    replies = [*plan_replies, *(r for _, _, rs in results for r in rs), *enrich_replies]
    write_metrics(chapter, "layer", len(layer["nodes"]), replies)
    broken = [n for n, found in report["issues"].items() if any(i.startswith("схема") for i in found)]
    if broken:
        raise SystemExit(f"узлы не прошли схему: {', '.join(broken)}; слой сохранён, повторите команду")
    log.info("слой: узлов %s, утверждений %s, отброшено %s, замечания в узлах: %s, $%.2f", report["nodes"], report["claims"],
             len(report["dropped_claims"]), len(report["issues"]), sum(r.cost_usd for r in replies))
    return layer


def build_routing(chapter: Chapter, provider: Provider) -> None:
    templates = "\n".join(load_templates(chapter.domain / "templates"))
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


def build_illustrations(chapter: Chapter, provider: Provider) -> None:
    nodes = read(chapter.work / "layer.json")["nodes"]
    templates, style = load_templates(chapter.domain / "templates"), load_style(chapter.domain)
    prompt = prompt_file("illustrations")
    errata = read_or(chapter.errata_file, {"entries": []})["entries"]

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


def read_or(path: Path, default: Any) -> Any:
    return read(path) if path.exists() else default


def build_site(chapter: Chapter) -> Path:
    work = chapter.work
    out = build_course(read(work / "layer.json"), read_or(work / "routing.json", {"routes": []}), read_or(work / "tasks.json", {"tasks": []})["tasks"],
                       read_or(work / "illustrations.json", {"illustrations": []})["illustrations"], ROOT / "out" / chapter.chapter_id, work / "pictures")
    log.info("курс: %s", out / "index.html")
    return out


def build_review(chapter: Chapter, source: Path, provider: Provider) -> Path:
    """Проверка чужого пакета; ответ — out/review/<пакет>.json."""
    package = load_package(source)
    folder = workspace(source, ROOT / "work" / "review", package["package_id"])
    prompts = {role: prompt_file(f"review_{role}") for role in ("find", "physics", "judge")}
    checklist = (chapter.domain / "physics_checklist.json").read_text(encoding="utf-8")
    answer, replies = review_package(package, pages_of(chapter.units), provider, prompts, checklist, folder)
    target = ROOT / "out" / "review" / f"{package['package_id']}.json"
    save(target, answer)
    write_metrics(chapter, "review", len(package["items"]) + len(package["frames"]), replies)
    log.info("замечаний %s, $%.2f, ответ: %s", len(answer["remarks"]), sum(r.cost_usd for r in replies), target)
    return target


def build_video(chapter: Chapter, provider: Provider, node_id: str, kind: str, template_name: str) -> None:
    """Ролик по одному узлу. Нужны пакеты группы video (pycairo, edge-tts, faster-whisper) и ffmpeg."""
    from glava.scenes import load_module
    from glava.video.produce import produce
    from glava.video.spec import make_spec

    node = next((n for n in read(chapter.work / "layer.json")["nodes"] if n["id"] == node_id), None)
    if node is None:
        raise SystemExit(f"узла {node_id} нет в слое")
    template = load_module(chapter.domain / "video" / f"{template_name}.py")
    checklist = read(chapter.domain / "physics_checklist.json")
    video_id = f"{node_id.replace('.', '_')}_{kind}"
    spec, replies = make_spec(provider, prompt_file("video"), node, template, template_name, checklist, kind, video_id, chapter.chapter_id)
    passport = produce(spec, node, template, load_style(chapter.domain), (chapter.domain / "pronunciation.md").read_text(encoding="utf-8"), checklist,
                       chapter.work / "videos", ROOT / "out" / chapter.chapter_id / "videos")
    write_metrics(chapter, "video", 1, replies, passport["audio_check"]["duration_s"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="glava", description="Глава книги -> учебный слой -> демо-курс")
    parser.add_argument("command", choices=["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "review", "video", "units"])
    parser.add_argument("chapter")
    parser.add_argument("--limit", type=int, default=None, help="собрать только первые N узлов")
    parser.add_argument("--package", type=Path, default=None, help="папка чужого пакета для review")
    parser.add_argument("--node", help="узел для video")
    parser.add_argument("--format", choices=["short", "wide"], default="short", help="формат ролика")
    parser.add_argument("--template", help="шаблон сцены ролика из доменного пакета")
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
    provider = cached(metered(provider_from_env(), BUDGET_USD), ROOT / ".cache")
    if args.command == "review":
        if args.package is None:
            parser.error("укажите --package")
        build_review(chapter, args.package, provider)
        return
    if args.command == "video":
        if not args.node or not args.template:
            parser.error("укажите --node и --template")
        build_video(chapter, provider, args.node, args.format, args.template)
        return
    if args.command in ("build", "errata"):
        build_errata(chapter, provider)
    if args.command in ("build", "layer"):
        build_layer(chapter, provider, args.limit)
    if args.command in ("build", "routing"):
        build_routing(chapter, provider)
    if args.command in ("build", "tasks"):
        build_tasks(chapter, provider)
    if args.command in ("build", "illustrations"):
        build_illustrations(chapter, provider)
    if args.command == "build":
        build_site(chapter)


if __name__ == "__main__":
    main()
