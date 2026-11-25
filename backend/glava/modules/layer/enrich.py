"""Дополнение узлов до состава страницы шага из ТЗ: суть, порядок действий, формулы, «как сейчас», ручной труд."""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from glava.modules.errata.api import for_pages, prompt_block
from glava.modules.llm.api import Provider, Reply, ask_json
from glava.modules.source_text.api import Unit, book_tables, number_blocks
from glava.shared.evidence import unsupported_numbers

SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[«\"(]?[А-ЯЁA-Z])")
MAX_WORDS = 20
MAX_STEP_WORDS = 25
TITLE_WORDS = (3, 7)
ESSENCE_SENTENCES = (2, 3)
LENS_FIELDS = ("inputs", "manual_steps", "judgment_points", "time", "typical_errors")


def sentences(text: str) -> list[str]:
    return [s for s in SENTENCE.split(text.strip()) if s.strip()]


def _source(node: Mapping[str, Any]) -> str:
    claims = " ".join(f"{c['text']} {c['quote']}" for c in node["claims"])
    return f"{claims} {json.dumps(node.get('worked_examples') or [], ensure_ascii=False)} {json.dumps(node.get('book_tasks') or [], ensure_ascii=False)}"


def _text_problems(row: Mapping[str, Any], source: str) -> list[str]:
    parts = sentences(row["essence"])
    problems = [] if ESSENCE_SENTENCES[0] <= len(parts) <= ESSENCE_SENTENCES[1] else [f"essence: фраз {len(parts)}, нужно 2–3"]
    problems += [f"essence: фраза длиннее {MAX_WORDS} слов" for p in parts if len(p.split()) > MAX_WORDS]
    if not TITLE_WORDS[0] <= len(row["short_title"].split()) <= TITLE_WORDS[1]:
        problems.append("short_title: нужно 3–7 слов")
    lens = row["inefficiency_lens"]
    if lens is not None and any(not str(lens.get(f) or "").strip() for f in LENS_FIELDS):
        problems.append(f"inefficiency_lens: нужны все поля {LENS_FIELDS}")
    shown = " ; ".join([row["essence"], row["short_title"], row["now_practice"] or "", *(str(lens.get(f)) for f in LENS_FIELDS if lens)])
    foreign = unsupported_numbers(shown, source)
    return problems + ([f"чисел нет в утверждениях узла: {', '.join(sorted(foreign))}"] if foreign else [])


def _block_problems(row: Mapping[str, Any], claims: set[str], source: str) -> list[str]:
    problems: list[str] = []
    steps, formulas = row["procedure"], row["formulas"]
    if len(steps) == 1:
        problems.append("procedure: один шаг — это не порядок действий")
    problems += [f"procedure: утверждения {s['claim_id']} нет в узле" for s in steps if s["claim_id"] not in claims]
    problems += [f"procedure: шаг длиннее {MAX_STEP_WORDS} слов" for s in steps if len(s["text"].split()) > MAX_STEP_WORDS]
    for f in formulas:
        if f["claim_id"] not in claims:
            problems.append(f"formulas: утверждения {f['claim_id']} нет в узле")
        if not f["tex"].strip() or f["tex"].count("{") != f["tex"].count("}"):
            problems.append("formulas: скобки не сходятся")
        if not f["legend"] or any(not str(x.get("symbol") or "").strip() or not str(x.get("meaning") or "").strip() for x in f["legend"]):
            problems.append("formulas: нужна расшифровка каждого обозначения")
    shown = " ; ".join([*(s["text"] for s in steps), *(f["tex"] for f in formulas), *(str(x) for f in formulas for x in f["legend"])])
    foreign = unsupported_numbers(shown, source) - {"1", "2"}
    return problems + ([f"procedure, formulas: чисел нет в узле: {', '.join(sorted(foreign))}"] if foreign else [])


def row_issues(row: Mapping[str, Any], node: Mapping[str, Any]) -> list[str]:
    source = _source(node)
    return _text_problems(row, source) + _block_problems(row, {c["id"] for c in node["claims"]}, source)


def enrich_issues(data: Any, nodes: Sequence[Mapping]) -> list[str]:
    by_id = {n["id"]: n for n in nodes}
    issues: list[str] = []
    for row in data["nodes"]:
        node = by_id.get(row.get("node_id"))
        issues += [f"{row.get('node_id')}: {p}" for p in row_issues(row, node)] if node else [f"узла {row.get('node_id')} нет"]
    done = {r.get("node_id") for r in data["nodes"]}
    return issues + [f"{n}: узел пропущен" for n in by_id if n not in done]


def _valid(row: Any, node: Mapping[str, Any]) -> bool:
    try:
        return not row_issues(row, node)
    except (KeyError, TypeError, AttributeError):
        return False


def _brief(node: Mapping[str, Any]) -> dict[str, Any]:
    return {"node_id": node["id"], "title": node["title"], "short_title": node["short_title"], "main": node["layers"]["main"]["text"],
            "practice": node["layers"]["practice"]["text"], "lens": node.get("inefficiency_lens"),
            "claims": [{"id": c["id"], "page": c["page_pdf"], "text": c["text"], "quote": c["quote"]} for c in node["claims"]]}


def make_enrichment(
    provider: Provider, system: str, nodes: Sequence[Mapping], now_practice: str, errata: Sequence[Mapping] = (),
) -> tuple[dict[str, dict], list[Reply]]:
    pages = sorted({p for n in nodes for p in n["pages"]})
    prompt = (f"# Как сейчас (справка домена)\n{now_practice or 'справки нет'}\n\n# Узлы\n{json.dumps([_brief(n) for n in nodes], ensure_ascii=False, indent=0)}"
              + prompt_block(for_pages(errata, pages)))
    data, replies = ask_json(provider, system, prompt, lambda d: enrich_issues(d, nodes))
    by_id = {n["id"]: n for n in nodes}
    return {r["node_id"]: r for r in data["nodes"] if isinstance(r, dict) and r.get("node_id") in by_id and _valid(r, by_id[r["node_id"]])}, replies


def apply(node: Mapping[str, Any], row: Mapping[str, Any] | None, units: Sequence[Unit], errata: Sequence[Mapping]) -> dict[str, Any]:
    """Узел с блоками страницы. Без строки от модели добавляются только блоки, которые собирает код."""
    done = {**node, "numbers": number_blocks(node), "tables": book_tables(node, units, errata), "procedure": [], "formulas": []}
    if row is None:
        return done
    page = {c["id"]: c["page_pdf"] for c in node["claims"]}
    fixed = {e["page"] for e in errata if e["kind"] == "recognition"}
    lens = row["inefficiency_lens"]
    return {
        **done, "short_title": row["short_title"], "layers": {**node["layers"], "main": {"text": row["essence"], "by_model": True}},
        "now_practice": {"text": row["now_practice"], "by_model": True} if row["now_practice"] else node.get("now_practice"),
        "inefficiency_lens": {**{f: lens[f] for f in LENS_FIELDS}, "by_model": True} if lens and not node.get("inefficiency_lens") else node.get("inefficiency_lens"),
        "procedure": [{"text": s["text"], "pages": [page[s["claim_id"]]], "claim_id": s["claim_id"]} for s in row["procedure"]],
        "formulas": [{"tex": f["tex"], "page": page[f["claim_id"]], "claim_id": f["claim_id"], "legend": f["legend"],
                      "errata": "обозначения сверены со сканом страницы" if page[f["claim_id"]] in fixed else None} for f in row["formulas"]],
    }
