"""Учебный слой: план узлов по единицам главы -> узлы с цитатами -> таблица покрытия."""

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from glava.llm import Provider, Reply, ask_json
from glava.stages.wording import normal_layers, plain_node
from glava.units import Unit
from glava.verify import find_quote_page, unsupported_numbers, verify_layer

SCHEMAS = Path(__file__).parent.parent / "schemas"
SLUG = re.compile(r"^[a-z0-9_]+$")
SKIPPABLE_KINDS = {"heading"}
SHORT_JUNK_CHARS = 40
FORBIDDEN_REASON = re.compile(r"непоказ|подробн|не важн|вторичн", re.IGNORECASE)


@lru_cache
def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def pages_of(units: Sequence[Unit]) -> dict[int, str]:
    pages: dict[int, str] = {}
    for unit in units:
        pages = {**pages, unit.page_pdf: f"{pages.get(unit.page_pdf, '')}\n\n{unit.text}"}
    return pages


def plan_issues(plan: Mapping, units: Sequence[Unit]) -> list[str]:
    by_id = {u.unit_id: u for u in units}
    placed = {uid for n in plan["nodes"] for uid in n["unit_ids"]}
    skipped = {s["unit_id"]: s["reason"] for s in plan.get("skipped", [])}
    issues = [f"единица {u} не вошла ни в один узел" for u in by_id if u not in placed and u not in skipped]
    issues += [f"единицы {u} нет в главе" for u in placed | set(skipped) if u not in by_id]
    for uid, reason in skipped.items():
        unit = by_id.get(uid)
        if unit and uid not in placed and (FORBIDDEN_REASON.search(reason) or not reason.strip()
                                           or (unit.kind not in SKIPPABLE_KINDS and len(unit.text) > SHORT_JUNK_CHARS)):
            issues.append(f"единицу {uid} ({unit.kind}) нельзя пропустить: {reason}")
    slugs = Counter(n["slug"] for n in plan["nodes"])
    issues += [f"slug {s} повторяется или не латиницей" for s, count in slugs.items() if count > 1 or not SLUG.match(s)]
    terms = Counter(t.casefold() for n in plan["nodes"] for t in n["terms_introduced"])
    issues += [f"термин «{t}» объясняется в {count} узлах" for t, count in terms.items() if count > 1]
    in_parts = [s for p in plan.get("parts", []) for s in p["slugs"]]
    if sorted(in_parts) != sorted(slugs):
        issues.append("parts должны перечислять каждый slug ровно один раз")
    return issues


def assemble_node(raw: Mapping, plan_node: Mapping, order: int, prefix: str, units: Sequence[Unit]) -> dict[str, Any]:
    """Ответ модели + служебные поля, которые ставит код: id, порядок, страницы, связи."""
    node_id = f"{prefix}.{plan_node['slug']}"
    used = {u.unit_id: u for u in units if u.unit_id in set(plan_node["unit_ids"])}
    claims = [{"page_print": None, **c, "id": f"{node_id}#c{i}"} for i, c in enumerate(raw["claims"], start=1)]
    links = [{"type": "prerequisite", "target": f"{prefix}.{slug}"} for slug in raw.get("prerequisites", [])]
    ref = (raw.get("misconception") or {}).get("ref")
    links += [{"type": "refutes_misconception", "target": ref}] if ref else []
    kept = {k: v for k, v in raw.items() if k not in {"claims", "prerequisites"}}
    if isinstance(kept.get("layers"), Mapping):
        kept = {**kept, "layers": normal_layers(kept["layers"])}
    return {
        **kept, "id": node_id, "order": order, "title": plan_node["title"], "short_title": plan_node["short_title"],
        "why_here": {"text": plan_node["why_here"], "by_model": True}, "difficulty": plan_node["difficulty"],
        "threshold": plan_node["threshold"], "pages": sorted({u.page_pdf for u in used.values()}), "claims": claims,
        "links": links, "terms_introduced": plan_node["terms_introduced"], "unit_ids": list(plan_node["unit_ids"]),
    }


def _schema_issues(node: Mapping) -> list[str]:
    schema = load_schema("node")
    validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/node", "$defs": schema["$defs"]})
    return [f"схема: {'/'.join(map(str, e.absolute_path))}: {e.message[:160]}" for e in validator.iter_errors(node)]


def node_issues(node: Mapping, units: Sequence[Unit], plan_node: Mapping) -> list[str]:
    schema_problems = _schema_issues(node)
    if schema_problems:
        return schema_problems
    pages = pages_of(units)
    issues = [f"{i.where}: {i.message}" for i in verify_layer({"nodes": [node]}, pages)]
    cited = {c.get("unit_id") for c in node["claims"]}
    example_pages = {e["page_pdf"] for e in (*node.get("worked_examples", []), *node.get("book_tasks", []))}
    for unit in units:
        if unit.unit_id not in plan_node["unit_ids"] or unit.kind == "heading" or len(unit.text) <= SHORT_JUNK_CHARS:
            continue
        backed_by_task = unit.kind == "task" and unit.page_pdf in example_pages
        if unit.unit_id not in cited and not backed_by_task:
            issues.append(f"единица {unit.unit_id} ({unit.kind}) не подтверждает ни одного утверждения: «{unit.excerpt}…»")
    return issues


def coverage_rows(plan: Mapping, units: Sequence[Unit], prefix: str) -> list[dict[str, Any]]:
    reasons = {s["unit_id"]: s["reason"] for s in plan.get("skipped", [])}
    homes = {u.unit_id: [f"{prefix}.{n['slug']}" for n in plan["nodes"] if u.unit_id in n["unit_ids"]] for u in units}
    return [{"unit_id": u.unit_id, "kind": u.kind, "page_pdf": u.page_pdf, "excerpt": u.excerpt, "node_ids": homes[u.unit_id],
             "reason": None if homes[u.unit_id] else reasons.get(u.unit_id)} for u in units]


def _unit_text(unit: Unit) -> str:
    mark = " [описание распознавателя]" if unit.by_recogniser else ""
    return f"[{unit.unit_id} · {unit.kind} · стр. {unit.page_pdf}]{mark}\n{unit.text}"


def make_plan(provider: Provider, system: str, context: str, units: Sequence[Unit]) -> tuple[dict, list[Reply]]:
    prompt = f"{context}\n\n# Единицы главы\n\n" + "\n\n".join(_unit_text(u) for u in units)
    return ask_json(provider, system, prompt, lambda d: plan_issues(d, units), attempts=3)


def make_node(
    provider: Provider, system: str, context: str, plan: Mapping, index: int, units: Sequence[Unit], prefix: str,
) -> tuple[dict, list[str], list[Reply]]:
    plan_node = plan["nodes"][index]
    earlier = plan["nodes"][:index]
    known = ", ".join(t for n in earlier for t in n["terms_introduced"]) or "пока ничего"
    own = [u for u in units if u.unit_id in set(plan_node["unit_ids"])]
    prompt = (f"{context}\n\n# Узел\n{json.dumps(plan_node, ensure_ascii=False)}\n\n# Узлы до него (slug: название)\n"
              + ("\n".join(f"{n['slug']}: {n['title']}" for n in earlier) or "это первый узел")
              + f"\n\n# Уже объяснены\n{known}\n\n# Единицы узла\n\n" + "\n\n".join(_unit_text(u) for u in own))
    pages = pages_of(units)

    def check(raw: Mapping) -> list[str]:
        return node_issues(assemble_node(raw, plan_node, index + 1, prefix, units), units, plan_node)

    raw, replies = ask_json(provider, system, prompt, check, attempts=3)
    node = repair_pages(assemble_node(raw, plan_node, index + 1, prefix, units), pages)
    return node, node_issues(node, units, plan_node), replies


def repair_pages(node: Mapping, pages: Mapping[int, str]) -> dict[str, Any]:
    """Страница утверждения ставится по месту цитаты: если модель ошиблась номером, код его знает точно."""
    claims = [{**c, "page_pdf": find_quote_page(c["quote"], pages) or c["page_pdf"]} for c in node["claims"]]
    return {**node, "claims": claims}


def drop_unsupported(node: Mapping, pages: Mapping[int, str]) -> tuple[dict[str, Any], list[str]]:
    """Утверждения без найденной цитаты или с чужими числами не попадают в слой; список отдаётся в отчёт."""
    source = "\n".join(pages.values())
    good = [c for c in node["claims"] if find_quote_page(c["quote"], pages) and not unsupported_numbers(c["text"], source)]
    dropped = [c["id"] for c in node["claims"] if c not in good]
    return plain_node({**node, "claims": good}), dropped
