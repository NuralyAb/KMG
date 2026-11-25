"""verify: вторая модель сверяет слой."""

import logging
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from glava.modules.library.api import LibraryError
from glava.modules.llm.api import Provider, Reply
from glava.modules.metrics.api import append_metrics
from glava.modules.trust.api import (
    CLAIM_GROUP,
    check_claims,
    mutants,
    source_of,
    trust_report,
    verify_node,
)
from glava.pipeline.chapter import file_digest, layer_of
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import save
from glava.shared.language import is_english

MODEL_MUTANTS = 20
log = logging.getLogger("glava")


def build_verify(chapter_id: str, provider: Provider, with_mutants: bool) -> dict[str, Any]:
    """Платно: вторая модель сверяет утверждения с цитатами и фразы с утверждениями."""
    work, layer = layer_of(chapter_id)
    digest = file_digest(work / "layer.json")  # пока модель отвечает, слой могут изменить
    english = is_english("\n".join(c["quote"] for n in layer["nodes"] for c in n["claims"]))
    prompts = {"claims": prompt_file("verify_claims", english), "prose": prompt_file("verify_prose", english)}
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda n: verify_node(provider, prompts, n), layer["nodes"]))
    report = trust_report(chapter_id, f"{provider.name}/{provider.model}", [c for cs, _, _ in results for c in cs], [p for _, ps, _ in results for p in ps], layer["nodes"])
    report["layer_sha256"] = digest
    replies = [r for _, _, rs in results for r in rs]
    if with_mutants:
        report["sensitivity"], asked = model_sensitivity(provider, prompts["claims"], layer, report)
        replies += asked
    save(work / "trust.json", report)
    append_metrics(chapter_id, "verify", len(layer["nodes"]), replies)
    log.info("утверждения: %s; фразы: %s; $%.2f", report["claims"], report["prose"], sum(r.cost_usd for r in replies))
    if report["claims"]["unchecked"] == report["claims"]["total"]:
        raise LibraryError("проверяющая модель не вынесла ни одного вердикта: ничего не проверено")
    return report


def model_sensitivity(provider: Provider, prompt: str, layer: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, Any], list[Reply]]:
    """Испорченные утверждения вперемешку с нетронутыми: видно и чутьё проверяющего, и ложные тревоги.

    Портятся только утверждения, которые он до порчи признал верными.
    """
    weak = {r["id"] for r in report["weak"]}
    claims = [c for n in layer["nodes"] for c in n["claims"] if c["id"] not in weak]
    shuffle = random.Random(0)
    made = list(mutants(claims, per_kind=MODEL_MUTANTS))
    calm = shuffle.sample(sorted(claims, key=lambda c: c["id"]), min(len(made), len(claims)))
    mixed = [(m.kind, m.text, m.quote) for m in made] + [("control", c["text"], source_of(c)) for c in calm]
    shuffle.shuffle(mixed)
    items = [{"id": f"m{i}", "text": text, "quote": quote} for i, (_, text, quote) in enumerate(mixed)]
    parts = [items[i:i + CLAIM_GROUP] for i in range(0, len(items), CLAIM_GROUP)]
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda p: check_claims(provider, prompt, p), parts))
    verdicts = {r["id"]: r["verdict"] for rows, _ in results for r in rows}
    rows: dict[str, dict[str, int]] = {}
    for i, (kind, _, _) in enumerate(mixed):
        if verdicts[f"m{i}"] != "unchecked":
            row = rows.setdefault(kind, {"made": 0, "caught": 0})
            row["made"] += 1
            row["caught"] += verdicts[f"m{i}"] != "follows"
    controls = rows.pop("control", {"made": 0, "caught": 0})
    total, caught = sum(k["made"] for k in rows.values()), sum(k["caught"] for k in rows.values())
    found = {"kinds": rows, "made": total, "caught": caught, "recall": round(caught / total, 3) if total else None, "controls": controls,
             "unchecked": sum(v == "unchecked" for v in verdicts.values())}
    return found, [r for _, rs in results for r in rs]
