"""Куда дошла правка: шаги, задания, рисунки, симуляторы, ролики."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from glava.modules.impact.diff import Change
from glava.modules.impact.spread import number_pattern, task_text

Row = Mapping[str, Any]


def _has_number(text: str, found: Iterable[Change]) -> bool:
    return any(number_pattern(n).search(text) for c in found for n in c.old_numbers)


def _linked(ids: Iterable[str | None], found: Sequence[Change]) -> list[Change]:
    wanted = set(ids)
    return [c for c in found if c.claim_id in wanted]


def _steps(nodes: Mapping[str, Row], touched: Iterable[str]) -> list[dict[str, Any]]:
    rows = [{"id": i, "title": nodes[i]["short_title"], "order": nodes[i]["order"]} if i in nodes else {"id": i, "title": i, "order": None} for i in touched]
    return sorted(rows, key=lambda s: (s["order"] is None, s["order"] or 0))


def _videos(passports: Mapping[str, Row], found: Sequence[Change]) -> list[dict[str, Any]]:
    rows = []
    for name, passport in passports.items():
        script = passport.get("script") or []
        linked = _linked([*(s.get("claim_id") for s in passport.get("sources") or []), *(b.get("claim_id") for b in script)], found)
        if linked:
            text = " ".join(str(b.get("text") or "") for b in script)
            rows.append({"id": name, "step_id": passport.get("node_id") or linked[0].node_id, "title": name, "is_certain": _has_number(text, linked)})
    return rows


def reach(
    layer: Row, found: Sequence[Change], fields: Mapping[str, Sequence[str]], tasks: Sequence[Row], pictures: Sequence[Row], picture_text: Mapping[str, str],
    simulations: Mapping[str, Sequence[Row]], passports: Mapping[str, Row],
) -> dict[str, list[dict[str, Any]]]:
    """is_certain — внутри стоит старое число; иначе место опирается на утверждение, и его нужно посмотреть."""
    nodes = {n["id"]: n for n in layer["nodes"]}
    task_rows = [{"id": t["id"], "step_id": t["step_id"], "title": t["prompt"], "is_certain": _has_number(task_text(t), linked)}
                 for t in tasks if (linked := _linked(t.get("claim_ids") or [], found))]
    picture_rows = [{"id": p["id"], "step_id": p["step_id"], "title": p.get("caption") or p["id"],
                     "is_certain": _has_number(f"{p.get('caption') or ''} {p.get('alt') or ''} {picture_text.get(p['id'], '')}", linked)}
                    for p in pictures if (linked := _linked(p.get("claim_ids") or [], found))]
    scenes = [{"id": s["scene"], "step_id": step, "title": s["scene"], "is_certain": False}
              for step, rows in simulations.items() for s in rows if _linked(s.get("claims") or [], found)]
    return {"steps": _steps(nodes, {c.node_id for c in found} | set(fields)), "tasks": task_rows, "pictures": picture_rows, "simulations": scenes,
            "videos": _videos(passports, found)}
