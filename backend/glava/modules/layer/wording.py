"""Выравнивание ответа модели: форма слоёв и слова, которые читателю ничего не говорят."""

import re
from collections.abc import Mapping
from typing import Any

PLACE = "этой части главы"
UNTOUCHED = {"quote", "id", "unit_id", "unit_ids", "claim_ids", "ref", "target", "links", "term"}
CASES = {"узел": "шаг", "узла": "шага", "узлу": "шагу", "узлом": "шагом", "узле": "шаге", "узлы": "шаги", "узлов": "шагов", "узлам": "шагам",
         "узлами": "шагами", "узлах": "шагах",
         "распознаватель": "программа распознавания", "распознавателя": "программы распознавания", "распознавателем": "программой распознавания",
         "распознавателю": "программе распознавания"}
RULES = (
    (r"в тексте единицы", "в тексте главы"),
    (r"в (?:этих|данных)(?: двух| трёх| трех)? (?:единицах|абзацах)(?: узла)?", f"в {PLACE}"),
    (r"в этой единице(?: узла)?", f"в {PLACE}"),
    (r"в единицах узла", f"в {PLACE}"),
    (r"в единицах(?= (?:не |нет\b|отсутств)|[.,;])", f"в {PLACE}"),
    (r"в единице(?= (?:не |нет\b|отсутств|искаж))", f"в {PLACE}"),
    (r"в выданном тексте", "в тексте главы"),
    (r"единицы узла", "текст шага"),
    (r"\bединица не\b", "глава здесь не"),
)


def _same_case(source: str, target: str) -> str:
    return target[0].upper() + target[1:] if source[:1].isupper() else target


def plain_text(text: str) -> str:
    for pattern, target in RULES:
        text = re.sub(pattern, lambda m, t=target: _same_case(m.group(), t), text, flags=re.IGNORECASE)
    return re.sub(r"\b\w+\b", lambda m: _same_case(m.group(), CASES[m.group().lower()]) if m.group().lower() in CASES else m.group(), text)


def plain_node(value: Any, key: str = "") -> Any:
    if key in UNTOUCHED:
        return value
    if isinstance(value, str):
        return plain_text(value)
    if isinstance(value, Mapping):
        return {k: plain_node(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [plain_node(v, key) for v in value]
    return value


def normal_layers(layers: Mapping[str, Any]) -> dict[str, Any]:
    deeper = layers.get("deeper") or []
    items = deeper if isinstance(deeper, list) else [deeper]
    return {**layers, "deeper": [{"text": i, "by_model": True} if isinstance(i, str) else i for i in items]}
