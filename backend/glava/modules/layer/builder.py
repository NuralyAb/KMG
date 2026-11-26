"""Учебный слой: план узлов по единицам главы -> узлы с цитатами -> таблица покрытия."""

import json
import os
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import jsonschema

from glava.modules.errata.api import for_pages, number_sources, prompt_block
from glava.modules.layer.wording import normal_layers, plain_node
from glava.modules.llm.api import CACHE_BREAK, Provider, Reply, ask_json
from glava.modules.source_text.api import Unit, is_english_source
from glava.shared.evidence import (
    bare_term,
    find_quote_page,
    node_source,
    node_texts,
    quote_on_page,
    restored_quote,
    whole_formula,
    unsupported_numbers,
    verify_layer,
    with_extra,
)
from glava.shared.json_schemas import load_schema
from glava.shared.language import is_untranslated

SLUG = re.compile(r"[a-z0-9_]+")
SKIPPABLE_KINDS = {"heading"}
SHORT_JUNK_CHARS = 40
FORBIDDEN_REASON = re.compile(r"непоказ|подробн|не важн|вторичн", re.IGNORECASE)


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
                                           or (unit.kind not in SKIPPABLE_KINDS and not unit.skippable and len(unit.text) > SHORT_JUNK_CHARS)):
            issues.append(f"единицу {uid} ({unit.kind}) нельзя пропустить: {reason}")
    slugs = Counter(n["slug"] for n in plan["nodes"])
    issues += [f"slug {s} повторяется или не латиницей" for s, count in slugs.items() if count > 1 or not SLUG.fullmatch(s)]
    terms = Counter(bare_term(t) for n in plan["nodes"] for t in n["terms_introduced"])
    issues += [f"термин «{t}» объясняется в {count} узлах" for t, count in terms.items() if count > 1]
    in_parts = [s for p in plan.get("parts", []) for s in p["slugs"]]
    if sorted(in_parts) != sorted(slugs):
        issues.append("parts должны перечислять каждый slug ровно один раз")
    if is_english_source(units):
        issues += [f"{n['slug']}: {field} на языке книги, нужен перевод на русский" for n in plan["nodes"] for field in ("title", "short_title", "why_here")
                   if is_untranslated(str(n[field]))]
        issues += [f"часть «{p['title']}» на языке книги, нужен перевод на русский" for p in plan["parts"] if is_untranslated(str(p["title"]))]
    return issues


def _with_exact_quotes(claim: Mapping[str, Any], own: Sequence[Unit], units: Sequence[Unit]) -> dict[str, Any]:
    """Английской цитате возвращается вид страницы, если модель поменяла кавычки, тире или сняла перенос. Русские цитаты не трогаются."""
    def exact(quote: Any, places: Sequence[Unit]) -> Any:
        if not isinstance(quote, str) or any(quote_on_page(quote, u.text) for u in places):
            return quote
        return next((found for u in places if (found := restored_quote(quote, u.text))), quote)

    given = claim.get("conditions")
    conditions = [{**x, "quote": exact(x["quote"], units)} if isinstance(x, Mapping) and "quote" in x else x for x in given] if isinstance(given, list) else given
    return {**claim, "quote": exact(claim["quote"], own), **({"conditions": conditions} if "conditions" in claim else {})}


def whole_formulas(claim: Mapping[str, Any], units: Sequence[Unit]) -> dict[str, Any]:
    """Цитата, оборванная внутри $$…$$, получает целую формулу из той единицы, где стоит; так же условия утверждения."""
    def whole(quote: Any) -> Any:
        if not isinstance(quote, str):
            return quote
        return next((w for u in units if quote_on_page(quote, u.text) and (w := whole_formula(quote, u.text)) != quote), quote)

    given = claim.get("conditions")
    conditions = [{**x, "quote": whole(x["quote"])} if isinstance(x, Mapping) and "quote" in x else x for x in given] if isinstance(given, list) else given
    return {**claim, "quote": whole(claim.get("quote")), **({"conditions": conditions} if "conditions" in claim else {})}


def _grounded(claim: Mapping[str, Any], units: Sequence[Unit]) -> dict[str, Any]:
    """Единицу и вид источника определяет место цитаты, а не модель."""
    home = [u for u in units if quote_on_page(claim["quote"], u.text)]
    if not home:
        return dict(claim)
    unit = next((u for u in home if u.unit_id == claim.get("unit_id")), home[0])
    by_machine = {"source_kind": "figure_description_model", "by_model": True} if all(u.by_recogniser for u in home) else {}
    return {**claim, "unit_id": unit.unit_id, **by_machine}


def mark_unsure_claims(node: Mapping[str, Any], units: Sequence[Unit]) -> dict[str, Any]:
    """Утверждение со страницы, которой нельзя верить, сверяют со сканом, даже если та же цитата есть на надёжной."""
    unsure = {u.page_pdf for u in units if u.needs_scan}
    return {**node, "claims": [{**c, "needs_scan": True} if c["page_pdf"] in unsure else c for c in node["claims"]]}


def assemble_node(raw: Mapping, plan_node: Mapping, order: int, prefix: str, units: Sequence[Unit]) -> dict[str, Any]:
    """Ответ модели + служебные поля, которые ставит код: id, порядок, страницы, связи."""
    node_id = f"{prefix}.{plan_node['slug']}"
    used = {u.unit_id: u for u in units if u.unit_id in set(plan_node["unit_ids"])}
    own = list(used.values())
    said = [_with_exact_quotes(c, own, units) for c in raw["claims"]] if is_english_source(units) else raw["claims"]
    said = [whole_formulas(c, units) for c in said]
    claims = [{"page_print": None, **_grounded(c, own), "id": f"{node_id}#c{i}"} for i, c in enumerate(said, start=1)]
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


def _is_condition(value: Any, pages: Mapping[int, str]) -> bool:
    return (isinstance(value, Mapping) and bool(str(value.get("text") or "").strip()) and isinstance(value.get("quote"), str)
            and find_quote_page(value["quote"], pages) is not None)


def node_issues(node: Mapping, units: Sequence[Unit], plan_node: Mapping, errata: Sequence[Mapping] = ()) -> list[str]:
    schema_problems = _schema_issues(node)
    if schema_problems:
        return schema_problems
    pages = pages_of(units)
    issues = [f"{i.where}: {i.message}" for i in verify_layer({"nodes": [node]}, pages, number_sources(errata))]
    own = {n: "\n\n".join(u.text for u in units if u.unit_id in plan_node["unit_ids"] and u.page_pdf == n) for n in pages}
    issues += [f"{c['id']}: цитата не из единиц узла, а из другого места главы" for c in node["claims"]
               if not any(quote_on_page(c["quote"], text) for text in own.values()) and find_quote_page(c["quote"], pages)]
    issues += [f"{c['id']}: условия нет в главе дословно: {str(x)[:80]}" for c in node["claims"] for x in c.get("conditions") or [] if not _is_condition(x, pages)]
    if is_english_source(units):
        issues += [f"{where}: текст на языке книги, нужен перевод на русский" for where, text in node_texts(node) if is_untranslated(text)]
    cited = {c.get("unit_id") for c in node["claims"]}
    example_pages = {e["page_pdf"] for e in (*node.get("worked_examples", []), *node.get("book_tasks", []))}
    for unit in units:
        if unit.unit_id not in plan_node["unit_ids"] or unit.kind == "heading" or unit.skippable or len(unit.text) <= SHORT_JUNK_CHARS:
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


def chapter_block(units: Sequence[Unit], env: Mapping[str, str] = os.environ) -> str:
    """Вся глава перед узлом: условие или обозначение, введённое в другом абзаце, иначе потеряется.

    Одинаковое начало запроса поставщик кэширует. Модели с коротким контекстом: GLAVA_CONTEXT=node.
    """
    if env.get("GLAVA_CONTEXT", "chapter") != "chapter":
        return ""
    return "\n\n# Вся глава, только для понимания\n\n" + "\n\n".join(_unit_text(u) for u in units)


def shared_units(plan: Mapping, index: int) -> str:
    """Единицы узла, которые план отдал и другим узлам. Длинный английский абзац план делит между узлами,
    а узел пересказывал его целиком: в курсе выходили два шага с одними и теми же утверждениями. Русский запрос не меняется."""
    own = plan["nodes"][index]
    others = [(uid, n) for uid in own["unit_ids"] for i, n in enumerate(plan["nodes"]) if i != index and uid in n["unit_ids"]]
    if not others:
        return ""
    rows = "\n".join(f"{uid}: также в узле «{n['title']}» ({n['slug']})" for uid, n in others)
    return ("\n\n# Единицы, общие с другими узлами\n" + rows
            + "\nИз такой единицы бери только то, что относится к теме этого узла; остальное утвердит другой узел. Не пересказывай её целиком.")


def make_node(
    provider: Provider, system: str, context: str, plan: Mapping, index: int, units: Sequence[Unit], prefix: str, errata: Sequence[Mapping] = (),
) -> tuple[dict, list[str], list[Reply]]:
    plan_node = plan["nodes"][index]
    earlier = plan["nodes"][:index]
    known = ", ".join(t for n in earlier for t in n["terms_introduced"]) or "пока ничего"
    own = [u for u in units if u.unit_id in set(plan_node["unit_ids"])]
    prompt = (f"{context}{chapter_block(units)}{CACHE_BREAK}# Узел\n{json.dumps(plan_node, ensure_ascii=False)}\n\n# Узлы до него (slug: название)\n"
              + ("\n".join(f"{n['slug']}: {n['title']}" for n in earlier) or "это первый узел")
              + f"\n\n# Уже объяснены\n{known}\n\n# Единицы узла\n\n" + "\n\n".join(_unit_text(u) for u in own)
              + prompt_block(for_pages(errata, sorted({u.page_pdf for u in own})))
              + (shared_units(plan, index) if is_english_source(units) else ""))
    pages = pages_of(units)

    def check(raw: Mapping) -> list[str]:
        return node_issues(assemble_node(raw, plan_node, index + 1, prefix, units), units, plan_node, errata)

    raw, replies = ask_json(provider, system, prompt, check, attempts=3)
    node = mark_unsure_claims(repair_pages(assemble_node(raw, plan_node, index + 1, prefix, units), pages), units)
    return node, node_issues(node, units, plan_node, errata), replies


def repair_pages(node: Mapping, pages: Mapping[int, str]) -> dict[str, Any]:
    """Страница утверждения ставится по месту цитаты: если модель ошиблась номером, код его знает точно."""
    def page(claim: Mapping[str, Any]) -> int:
        own = claim["page_pdf"]
        return own if quote_on_page(claim["quote"], pages.get(own, "")) else find_quote_page(claim["quote"], pages) or own

    claims = [{**c, "page_pdf": page(c)} for c in node["claims"]]
    return {**node, "claims": claims}


def drop_unsupported(node: Mapping, pages: Mapping[int, str], errata: Sequence[Mapping] = ()) -> tuple[dict[str, Any], list[str]]:
    """Утверждения без найденной цитаты или с чужими числами не попадают в слой; список отдаётся в отчёт."""
    source = node_source(node, with_extra(pages, number_sources(errata)))
    good = [c for c in node["claims"] if find_quote_page(c["quote"], pages) and not unsupported_numbers(c["text"], source)]
    dropped = [c["id"] for c in node["claims"] if c not in good]
    return plain_node({**node, "claims": good}), dropped
