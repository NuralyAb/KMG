"""Вторая модель сверяет слой с источником: следует ли утверждение из цитаты, а фраза текста — из утверждений узла.

Проверяющий не видит, кто писал слой, и ничего не исправляет: он только выносит вердикт, а код его считает.
"""

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from glava.modules.layer.api import sentences
from glava.modules.llm.api import Provider, Reply, ask_json
from glava.shared.evidence import node_texts

VERDICTS = ("follows", "partial", "no", "contradicts")
BAD = ("no", "contradicts")
# остальное (аналогии, гипотезы, «как сейчас») курс показывает как слова модели, а примеры и задачи — текст книги
CHECKED = ("layers", "glossary", "data_meaning.from_chapter", "data_meaning.breaks", "decision_on_data")
MIN_WORDS = 4
CLAIM_GROUP, PROSE_GROUP = 20, 25


def claim_items(node: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"id": c["id"], "text": c["text"], "quote": source_of(c)} for c in node["claims"]]


def source_of(claim: Mapping[str, Any]) -> str:
    """Цитата вместе с местами, где введены условия утверждения."""
    return " … ".join([claim["quote"], *(x["quote"] for x in claim.get("conditions") or [] if isinstance(x, Mapping) and isinstance(x.get("quote"), str))])


def prose_items(node: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Фразы связного текста: их читатель видит первыми, а цитаты под ними нет."""
    rows = []
    for where, text in node_texts(node):
        if where.startswith(CHECKED):
            rows += [{"id": f"{node['id']}:{where}:{i}", "text": s} for i, s in enumerate(sentences(text), start=1) if len(s.split()) >= MIN_WORDS]
    return rows


def text_shares(node: Mapping[str, Any]) -> Counter[str]:
    """Сколько знаков текста узла куда попало: на проверку, слишком коротко для неё или помечено как слова модели и не проверяется."""
    shares: Counter[str] = Counter()
    for where, text in node_texts(node):
        if "#c" in where:
            continue
        for sentence in sentences(text):
            kind = "not_checked" if not where.startswith(CHECKED) else "checked" if len(sentence.split()) >= MIN_WORDS else "too_short"
            shares[kind] += len(sentence)
    return shares


def verdict_issues(data: Any, ids: Sequence[str], claims: set[str] | None) -> list[str]:
    """claims — допустимые опоры фразы; None — проверяются сами утверждения, опора им не нужна."""
    if not isinstance(data, Mapping) or not isinstance(data.get("verdicts"), list):
        return ["нужен объект с массивом verdicts"]
    rows = data["verdicts"]
    if not all(isinstance(r, Mapping) and isinstance(r.get("id"), str) and isinstance(r.get("verdict"), str) for r in rows):
        return ["у каждого вердикта должны быть строки id и verdict"]
    counts = Counter(r["id"] for r in rows)
    issues = [f"{i}: вердиктов {counts[i]}, нужен один" for i in ids if counts[i] != 1]
    issues += [f"{i}: такого элемента нет" for i in counts if i not in ids]
    for row in rows:
        if row["verdict"] not in VERDICTS:
            issues.append(f"verdict должен быть из {VERDICTS}")
        elif claims is not None:
            support = row.get("claim_ids")
            if not isinstance(support, list) or not set(map(str, support)) <= claims:
                issues.append(f"{row['id']}: claim_ids должны быть из утверждений узла")
            elif row["verdict"] in ("follows", "partial") and not support:
                issues.append(f"{row['id']}: вердикт {row['verdict']} без опоры")
    return issues


def _ask(provider: Provider, system: str, prompt: str, items: Sequence[Mapping[str, Any]], claims: set[str] | None) -> tuple[list[dict], list[Reply]]:
    ids = [i["id"] for i in items]
    try:
        data, replies = ask_json(provider, system, prompt, lambda d: verdict_issues(d, ids, claims), attempts=2)
    except ValueError:
        data, replies = None, []
    if verdict_issues(data, ids, claims):
        # проверяющий не справился: непроверенное не выдаётся за проверенное
        return [{**i, "verdict": "unchecked", "why": "", "claim_ids": []} for i in items], replies
    by_id = {r["id"]: r for r in data["verdicts"]}
    return [{**i, "verdict": by_id[i["id"]]["verdict"], "why": str(by_id[i["id"]].get("why") or "")[:300],
             "claim_ids": list(by_id[i["id"]].get("claim_ids") or []) if claims is not None else []} for i in items], replies


def check_claims(provider: Provider, system: str, items: Sequence[Mapping[str, Any]]) -> tuple[list[dict], list[Reply]]:
    prompt = "# Утверждения и их цитаты\n" + json.dumps(list(items), ensure_ascii=False, indent=0)
    return _ask(provider, system, prompt, items, None)


def check_prose(provider: Provider, system: str, node: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> tuple[list[dict], list[Reply]]:
    claims = claim_items(node)
    prompt = (f"# Утверждения узла\n{json.dumps(claims, ensure_ascii=False, indent=0)}\n\n"
              f"# Фразы\n{json.dumps(list(items), ensure_ascii=False, indent=0)}")
    return _ask(provider, system, prompt, items, {c["id"] for c in claims})


def verify_node(provider: Provider, prompts: Mapping[str, str], node: Mapping[str, Any]) -> tuple[list[dict], list[dict], list[Reply]]:
    claims: list[dict] = []
    prose: list[dict] = []
    replies: list[Reply] = []
    for part in _batches(claim_items(node), CLAIM_GROUP):
        found, asked = check_claims(provider, prompts["claims"], part)
        claims, replies = [*claims, *found], [*replies, *asked]
    for part in _batches(prose_items(node), PROSE_GROUP):
        found, asked = check_prose(provider, prompts["prose"], node, part)
        prose, replies = [*prose, *found], [*replies, *asked]
    return claims, prose, replies


def _batches(values: Sequence[Any], size: int) -> list[Sequence[Any]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(r["verdict"] for r in rows)
    return {v: counts[v] for v in (*VERDICTS, "unchecked")} | {"total": len(rows)}


def trust_report(chapter: str, checker: str, claims: Sequence[Mapping[str, Any]], prose: Sequence[Mapping[str, Any]],
                 nodes: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    weak = [r for r in (*claims, *prose) if r["verdict"] != "follows"]
    chars = sum((text_shares(n) for n in nodes), Counter())
    # отправленное без вердикта не считается проверенным
    lost = sum(len(r["text"]) for r in prose if r["verdict"] == "unchecked")
    chars = Counter({**chars, "checked": chars["checked"] - lost, "unchecked": lost}) if lost else chars
    return {"chapter": chapter, "checker": checker, "claims": summary(claims), "prose": summary(prose), "weak": weak,
            "text_chars": dict(chars),
            "support": {r["id"]: r["claim_ids"] for r in prose if r["verdict"] in ("follows", "partial")}}
