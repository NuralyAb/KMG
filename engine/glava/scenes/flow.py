"""Схема решения или процесса: блоки по уровням, стрелки сверху вниз."""

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from glava.scenes.canvas import FONT, LINE, PAD, W, arrow, lines, rect, text, wrap

LABEL = "схема"
FRAME_CLASS = "B"
SUMMARY = """flow — схема решения или процесса: от данных к выводу, причина -> следствие. data: {"nodes":[{"id":"a","text":"до 60 знаков","kind":"data|step|choice|result"}],"edges":[{"from":"a","to":"b","label":"да/нет/условие до 14 знаков или пусто"}]}. 2–8 блоков; на одном уровне не больше двух; стрелка только на следующий уровень; без циклов."""
SCHEMA = {
    "type": "object", "required": ["nodes", "edges"], "additionalProperties": False,
    "properties": {
        "nodes": {"type": "array", "minItems": 2, "maxItems": 8, "items": {
            "type": "object", "required": ["id", "text", "kind"], "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "text": {"type": "string", "minLength": 2, "maxLength": 64},
                           "kind": {"enum": ["data", "step", "choice", "result"]}}}},
        "edges": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["from", "to"], "additionalProperties": False,
            "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "label": {"type": "string", "maxLength": 14}}}},
    },
}
GAP = 58
BOX_PAD = 14
PER_LEVEL = 2
BRANCH_LABELS = 15
HALF = (W - 2 * PAD - 16) / 2


def levels(data: Mapping[str, Any]) -> dict[str, int] | None:
    """Уровень блока — длина самого длинного пути к нему; None, если есть цикл или чужой блок."""
    ids = [n["id"] for n in data["nodes"]]
    if len(set(ids)) != len(ids) or any(e[k] not in ids for e in data["edges"] for k in ("from", "to")):
        return None
    level = dict.fromkeys(ids, 0)
    for _ in ids:
        moved = {e["to"]: level[e["from"]] + 1 for e in data["edges"] if level[e["to"]] <= level[e["from"]]}
        if not moved:
            return level
        level = {**level, **moved}
    return None


def check(data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    level = levels(data)
    if level is None:
        return ["в схеме цикл, повтор id или стрелка на блок, которого нет"]
    linked = {e[k] for e in data["edges"] for k in ("from", "to")}
    counts = defaultdict(int)
    for value in level.values():
        counts[value] += 1
    issues = [f"на уровне {k} блоков {v}, можно {PER_LEVEL}" for k, v in counts.items() if v > PER_LEVEL]
    issues += [f"стрелка {e['from']}->{e['to']} перескакивает уровень" for e in data["edges"] if level[e["to"]] - level[e["from"]] != 1]
    for source in level:
        labels = [e.get("label", "") for e in data["edges"] if e["from"] == source]
        if len(labels) > 1 and sum(map(len, labels)) > BRANCH_LABELS:
            issues.append(f"подписи стрелок из блока {source} вместе длиннее {BRANCH_LABELS} знаков")
    return issues + [f"блок {i} ни с чем не связан" for i in level if i not in linked]


def draw(data: Mapping[str, Any], style: Mapping[str, Any]) -> tuple[str, float]:
    level = levels(data) or {}
    accents = {"data": style["measurement"]["color"], "step": style["muted"], "choice": style["provenance"]["симуляция"],
               "result": style["provenance"]["реальные данные"]}
    by_level: dict[int, list[Mapping]] = defaultdict(list)
    for node in data["nodes"]:
        by_level[level[node["id"]]].append(node)
    boxes: dict[str, tuple[float, float, float, float]] = {}
    body, y = "", float(PAD)
    for number in sorted(by_level):
        row = by_level[number]
        width = HALF if len(row) == PER_LEVEL else W - 2 * PAD
        texts = [wrap(n["text"], width - 2 * BOX_PAD) for n in row]
        height = max(len(t) for t in texts) * LINE + 2 * BOX_PAD - 4
        for i, (node, rows) in enumerate(zip(row, texts, strict=True)):
            x = PAD + i * (width + 16)
            boxes[node["id"]] = (x, y, width, height)
            body += rect(x, y, width, height, style["panel"], radius=8, stroke=accents[node["kind"]], extra='stroke-width="2"')
            body += lines(x + width / 2, y + BOX_PAD + FONT - 2, rows, style["text"], "middle")
        y += height + GAP
    return body + _arrows(data, boxes, style), y - GAP + 12


def _arrows(data: Mapping[str, Any], boxes: Mapping[str, tuple[float, float, float, float]], style: Mapping[str, Any]) -> str:
    out = ""
    for edge in data["edges"]:
        (x1, y1, w1, h1), (x2, y2, w2, _) = boxes[edge["from"]], boxes[edge["to"]]
        narrow_x = (x2 + w2 / 2) if w2 <= w1 else (x1 + w1 / 2)
        end_x = narrow_x if w2 > w1 else x2 + w2 / 2
        start_x = narrow_x if w2 < w1 else x1 + w1 / 2
        out += arrow(start_x, y1 + h1 + 2, end_x, y2 - 3, style["muted"])
        label = edge.get("label", "")
        if label:
            right = end_x < W / 2 and len(label) * 12 < W - end_x - 30
            out += text(end_x + 14 if right else end_x - 14, (y1 + h1 + y2) / 2 + 7, label, style["text"], "start" if right else "end")
    return out
