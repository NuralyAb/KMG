"""Паспорт переноса: одна страница о том, насколько хорошо конвейер справился с главой. Только счёт, без модели."""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

Row = Mapping[str, Any]
TASK_TYPES = 5
MIN_TASKS = 15
MIN_TASK_TYPES = 4
MAX_MINUTES = 30
LINK_TYPES = {"prerequisite": "предпосылка", "example_of": "пример", "refutes_misconception": "опровергает заблуждение", "to_data": "переход к данным"}
SHOWN = ("шортс", "длинное видео", "интерактив")


def _check(key: str, title: str, value: str, target: str, state: str, note: str = "") -> dict[str, str]:
    """state: good, warn, bad, unknown. Неизмеренное не выдаётся за ноль."""
    return {"id": key, "title": title, "value": value, "target": target, "state": state, "note": note}


def _share(part: int, whole: int) -> str:
    return f"{part} из {whole}"


def _level(part: int, whole: int, warn: float = 0.9) -> str:
    if whole == 0:
        return "unknown"
    return "good" if part == whole else "warn" if part / whole >= warn else "bad"


def _layer_checks(layer: Row, coverage: Sequence[Row], audit: Row | None) -> list[dict[str, str]]:
    nodes = layer["nodes"]
    claims = [c for n in nodes for c in n["claims"]]
    placed = sum(bool(r.get("node_ids") or r.get("reason")) for r in coverage)
    sourced = sum(bool(c.get("quote") and c.get("page_pdf")) for c in claims)
    scan = sum(c.get("needs_scan") is True for c in claims)
    links = Counter(link["type"] for n in nodes for link in n.get("links") or [])
    lens = sum(bool(n.get("inefficiency_lens")) for n in nodes)
    rows = [
        _check("coverage", "Единицы главы: узел или причина", _share(placed, len(coverage)), "все", _level(placed, len(coverage), 0.98)),
        _check("quotes", "Утверждения с цитатой и страницей", _share(sourced, len(claims)), "все", _level(sourced, len(claims), 0.98)),
        _check("scan", "Утверждения, которые нужно сверить со сканом", str(scan), "0", "warn" if scan else "good", "числа и подписи, снятые с рисунков"),
        _check("links", "Типы связей между узлами", _share(len(links), len(LINK_TYPES)), "предпосылка, пример, опровержение, переход к данным",
               "good" if len(links) >= len(LINK_TYPES) else "warn", ", ".join(f"{LINK_TYPES.get(k, k)}: {v}" for k, v in sorted(links.items()))),
        _check("lens", "Линза неэффективности", _share(lens, len(nodes)), "все узлы", _level(lens, len(nodes))),
    ]
    if audit is None:
        return [*rows, _check("audit", "Расхождения с цитатами", "не проверяли", "разобраны все", "unknown", "бесплатно: glava audit")]
    sense = audit.get("sensitivity") or {}
    note = f"внесённой порчи поймано {sense.get('caught')} из {sense.get('made')}; без порчи помечено {sense.get('flagged_originals')}" if sense.get("made") else ""
    return [*rows, _check("audit", "Утверждения с расхождениями", str(len(audit["flagged"])), "разобраны все", "warn" if audit["flagged"] else "good", note),
            _check("terms", "Термины раньше объяснения", str(len(audit["early_terms"])), "0", "warn" if audit["early_terms"] else "good")]


def _course_checks(layer: Row, tasks: Sequence[Row], pictures: Sequence[Row], videos: int) -> list[dict[str, str]]:
    nodes = layer["nodes"]
    types = {t["type"] for t in tasks}
    drawn = {p["step_id"] for p in pictures}
    with_picture = sum(n["id"] in drawn for n in nodes)
    return [
        _check("tasks", "Задания", str(len(tasks)), f"не меньше {MIN_TASKS}", "good" if len(tasks) >= MIN_TASKS else "bad"),
        _check("types", "Типы заданий", _share(len(types), TASK_TYPES), f"не меньше {MIN_TASK_TYPES}", "good" if len(types) >= MIN_TASK_TYPES else "bad"),
        _check("pictures", "Шаги с иллюстрацией", _share(with_picture, len(nodes)), "все", _level(with_picture, len(nodes))),
        _check("decision", "Шаги «решение на данных»", str(sum(bool(n.get("decision_on_data")) for n in nodes)), "хотя бы один",
               "good" if any(n.get("decision_on_data") for n in nodes) else "bad"),
        _check("videos", "Ролики с паспортом", str(videos), "по назначению организаторов", "good" if videos else "unknown"),
    ]


def template_rows(layer: Row, routing: Sequence[Row], available: Iterable[str], scenes: Iterable[str]) -> list[dict[str, Any]]:
    """Отчёт о покрытии шаблонами: каждый узел, которому нужен показ в движении, — шаблон с моделью состояния или «нужен новый»."""
    known, ready = set(available), set(scenes)
    nodes = {n["id"]: n for n in layer["nodes"]}
    rows = []
    for route in routing:
        node = nodes.get(route["node_id"])
        if node is None or not {route.get("format"), route.get("secondary_format")} & set(SHOWN):
            continue
        template = route.get("template")
        state = "ready" if route["node_id"] in ready else "template" if template in known else "new"
        rows.append({"node_id": node["id"], "order": node["order"], "title": node["short_title"], "difficulty": node["difficulty"], "format": route["format"],
                     "score": sum((route.get("video_scores") or {}).values()), "template": template, "state": state})
    return sorted(rows, key=lambda r: (-r["score"], r["order"]))


def _labour(edits: Sequence[Row], chapter: str) -> dict[str, Any]:
    own = [e for e in edits if e.get("chapter") == chapter]
    measured = [float(e["person_minutes"]) for e in own if str(e.get("person_minutes") or "").strip()]
    return {"records": len(own), "measured": len(measured), "minutes": round(sum(measured), 1), "unmeasured": len(own) - len(measured)}


def _labour_check(labour: Row) -> dict[str, str]:
    if labour["unmeasured"]:
        return _check("labour", "Ручные правки", f"{labour['minutes']:g} мин, без минут записей: {labour['unmeasured']}", f"до {MAX_MINUTES} мин", "bad", "по записи без минут труд не посчитать")
    if labour["records"] == 0:
        return _check("labour", "Ручные правки", "записей нет", f"до {MAX_MINUTES} мин", "unknown", "ноль засчитают, если журнал совпадает с историей коммитов")
    return _check("labour", "Ручные правки", f"{labour['minutes']:g} мин", f"до {MAX_MINUTES} мин", "good" if labour["minutes"] <= MAX_MINUTES else "warn")


def _cost(metrics: Sequence[Row], chapter: str, nodes: int) -> dict[str, Any]:
    stages: dict[str, float] = {}
    for row in metrics:
        if row["chapter"] == chapter:
            stages[row["stage"]] = stages.get(row["stage"], 0.0) + float(row["money_usd"])
    total = sum(stages.values())
    return {"total_usd": round(total, 2), "per_node_usd": round(total / nodes, 2) if nodes else None, "stages": [{"stage": k, "usd": round(v, 2)} for k, v in stages.items()]}


def make_passport(
    layer: Row, coverage: Sequence[Row], routing: Sequence[Row], tasks: Sequence[Row], pictures: Sequence[Row], scenes: Iterable[str], videos: int,
    audit: Row | None, metrics: Sequence[Row], edits: Sequence[Row], templates: Iterable[str],
) -> dict[str, Any]:
    nodes = layer["nodes"]
    claims = [c for n in nodes for c in n["claims"]]
    labour = _labour(edits, layer["chapter"])
    rows = template_rows(layer, routing, templates, scenes)
    missing = [r for r in rows if r["state"] == "new"]
    checks = [*_layer_checks(layer, coverage, audit), *_course_checks(layer, tasks, pictures, videos),
              _check("templates", "Узлы с движением: есть шаблон", _share(len(rows) - len(missing), len(rows)), "все или «нужен новый»", _level(len(rows) - len(missing), len(rows), 0.7)),
              _labour_check(labour)]
    return {
        "chapter": layer["chapter"], "title": layer["title"], "book": layer["book"], "generated_by": layer.get("generated_by"),
        "counts": {"nodes": len(nodes), "claims": len(claims), "pages": len(layer.get("pdf_pages") or []), "by_model": sum(c.get("by_model") is True for c in claims)},
        "kinds": dict(Counter(c["kind"] for c in claims)), "checks": checks, "templates": rows, "cost": _cost(metrics, layer["chapter"], len(nodes)), "labour": labour,
        "scan_pages": sorted({c["page_pdf"] for c in claims if c.get("needs_scan")}),
    }
