"""layer: учебный слой главы."""

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from glava.modules.layer.api import (
    apply,
    coverage_rows,
    drop_unsupported,
    make_enrichment,
    make_node,
    make_plan,
    pages_of,
    plan_issues,
)
from glava.modules.llm.api import Provider, Reply
from glava.modules.tasks.api import groups
from glava.pipeline.chapter import Chapter, context_of, errata_of, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import save

log = logging.getLogger("glava")


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
    errata = errata_of(chapter)
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
