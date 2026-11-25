"""Чем слой отличается от того, по которому собран курс."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

from glava.modules.trust.api import claim_flags
from glava.shared.evidence import numbers_in

CLAIM_FIELDS = ("text", "quote", "page_pdf", "kind")
# эти расхождения с цитатой меняют смысл; остальные бывают законным пересказом
SERIOUS = frozenset({"number", "unit", "direction", "negation"})


@dataclass(frozen=True)
class Change:
    kind: Literal["changed", "added", "removed"]
    claim_id: str
    node_id: str
    before: str
    after: str
    quote: str
    page_pdf: int | None
    old_numbers: tuple[str, ...]
    new_numbers: tuple[str, ...]
    conflicts: tuple[str, ...]

    @property
    def is_serious(self) -> bool:
        return bool(SERIOUS & set(self.conflicts))

    def to_json(self) -> dict[str, Any]:
        return {**asdict(self), "is_serious": self.is_serious}


def _claim_rows(nodes: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {c["id"]: {**{f: c.get(f) for f in CLAIM_FIELDS}, "node_id": n["id"]} for n in nodes for c in n["claims"]}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def snapshot(layer: Mapping[str, Any]) -> dict[str, Any]:
    """След слоя, по которому собран курс: тексты утверждений целиком, остальные поля узла отпечатками."""
    return {"chapter": layer["chapter"], "claims": _claim_rows(layer["nodes"]),
            "nodes": {n["id"]: {k: _digest(v) for k, v in sorted(n.items()) if k not in ("claims", "id")} for n in layer["nodes"]}}


def snapshot_from_course(course: Mapping[str, Any]) -> dict[str, Any]:
    """Курс собрали до появления следов: утверждения есть в нём самом, отпечатков полей нет."""
    return {"chapter": course["id"], "claims": _claim_rows(course["steps"]), "nodes": {}}


def _change(kind: Literal["changed", "added", "removed"], claim_id: str, before: Mapping[str, Any], after: Mapping[str, Any]) -> Change:
    row = after or before
    old_text, new_text = before.get("text") or "", after.get("text") or ""
    old, new = numbers_in(old_text), numbers_in(new_text)
    # прежние расхождения уже разобраны: интересны только те, что внесла правка
    known = set(claim_flags(old_text, before["quote"])) if before else set()
    conflicts = [f for f in claim_flags(new_text, after["quote"]) if f not in known] if after else []
    return Change(kind, claim_id, row["node_id"], old_text, new_text, row["quote"], row["page_pdf"], tuple(sorted(old - new)), tuple(sorted(new - old)), tuple(conflicts))


def what_if(claim: Mapping[str, Any], node_id: str, text: str) -> Change:
    """Что было бы, если бы утверждение звучало так. Ничего не пишет."""
    return _change("changed", claim["id"], {**claim, "node_id": node_id}, {**claim, "text": text, "node_id": node_id})


def changes(before: Mapping[str, Any], layer: Mapping[str, Any]) -> tuple[list[Change], dict[str, list[str]]]:
    """Правки утверждений и изменённые поля узлов."""
    now = snapshot(layer)
    old, new = before["claims"], now["claims"]
    found = [_change("removed", i, old[i], {}) for i in old if i not in new]
    found += [_change("added", i, {}, new[i]) for i in new if i not in old]
    found += [_change("changed", i, old[i], new[i]) for i in new if i in old and any(old[i].get(f) != new[i].get(f) for f in CLAIM_FIELDS)]
    fields = {}
    for node_id, digests in now["nodes"].items():
        known = before["nodes"].get(node_id)
        if known is not None and (names := sorted(k for k in {*known, *digests} if known.get(k) != digests.get(k))):
            fields[node_id] = names
    return sorted(found, key=lambda c: c.claim_id), fields
