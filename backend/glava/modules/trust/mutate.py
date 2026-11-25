"""Проверка проверок: верные утверждения портятся известным способом, и видно, какую долю порчи проверка замечает."""

import random
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from glava.modules.source_text.api import BARE_REFERENCE, REFERENCE
from glava.modules.trust.audit import HEDGE, NEGATION, OPPOSITES, UNIT, claim_flags
from glava.modules.trust.entail import source_of

SWAPS = {
    "увеличивается": "уменьшается", "увеличиваются": "уменьшаются", "возрастает": "снижается", "возрастают": "снижаются", "повышается": "понижается",
    "повышаются": "понижаются", "растёт": "падает", "растет": "падает", "больше": "меньше", "выше": "ниже", "высокая": "низкая", "высокие": "низкие",
    "высокое": "низкое", "высокой": "низкой", "высоких": "низких", "максимальное": "минимальное", "максимальные": "минимальные", "увеличение": "уменьшение",
    "повышение": "понижение", "рост": "спад", "положительные": "отрицательные", "положительная": "отрицательная",
}
SWAPS |= {v: k for k, v in SWAPS.items()}
WORD = re.compile(r"[а-яё]+", re.IGNORECASE)
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w.,]*\d)")
OTHER_UNIT = {"%": "‰", "МПа": "кПа", "кПа": "МПа", "Па": "МПа", "мм": "см", "см": "м", "м": "км", "мкм": "мм", "км": "м", "мин": "ч", "ч": "сут", "сут": "ч", "с": "мин"}
PER_KIND = 60


@dataclass(frozen=True)
class Mutant:
    kind: str
    claim_id: str
    text: str
    quote: str


def _replace(text: str, match: re.Match[str], new: str, group: int = 0) -> str:
    return text[:match.start(group)] + new + text[match.end(group):]


def _flip(text: str) -> str | None:
    for match in WORD.finditer(text):
        new = SWAPS.get(match.group().casefold())
        if new:
            return _replace(text, match, new.capitalize() if match.group()[0].isupper() else new)
    return None


def _number(text: str) -> str | None:
    # номер рисунка или формулы — не величина: его порча смысла не меняет
    hidden = REFERENCE.sub(lambda m: "_" * len(m.group()), text)
    match = NUMBER.search(BARE_REFERENCE.sub(lambda m: "_" * len(m.group()), hidden))
    if not match:
        return None
    raw = match.group()
    digit = str((int(raw[0]) + 3) % 9 + 1)
    return _replace(text, match, digit + raw[1:])


def _unit(text: str) -> str | None:
    match = UNIT.search(text)
    return _replace(text, match, OTHER_UNIT[match.group(2)], 2) if match and match.group(2) in OTHER_UNIT else None


def _without_negation(text: str) -> str | None:
    match = re.search(r"\bне\s+", text, re.IGNORECASE)
    return _replace(text, match, "") if match else None


def _with_negation(text: str) -> str | None:
    match = re.search(r"\b(?=(?:зависит|зависят|влияет|влияют|позволяет|позволяют|меняется|меняются|показывает|показывают|даёт|дают|применяют|используют|определяют|выделяют|"
                      r"оценивают|лежит|соответствует|соответствуют|характеризуется)\b)", text)
    return _replace(text, match, "не ") if match and not NEGATION.search(text) else None


def _without_condition(text: str) -> str | None:
    match = re.search(r"\b(?:обычно|часто|иногда|примерно|около|преимущественно|в основном|как правило,?|в отдельных случаях|в некоторых случаях|возможно,?|вероятно,?)\s+", text, re.IGNORECASE)
    if match:
        return _replace(text, match, "")
    clause = re.search(r",?\s*(?:если|при условии)[^,.;]*[,.;]?", text, re.IGNORECASE)
    rest = _replace(text, clause, "") if clause else ""
    return rest.strip() if len(rest.split()) >= 4 else None


def _always(text: str) -> str | None:
    match = re.search(r"\b(?:обычно|часто|иногда|как правило,?|в основном)\b", text, re.IGNORECASE)
    if match:
        return _replace(text, match, "всегда")
    return f"Всегда и для любых условий: {text}" if len(text.split()) >= 4 else None


MUTATORS: Mapping[str, Callable[[str], str | None]] = {
    "sign_flip": _flip, "number": _number, "unit": _unit, "negation_removed": _without_negation, "negation_added": _with_negation,
    "lost_condition": _without_condition, "overgeneralization": _always,
}


def mutants(claims: Sequence[Mapping[str, Any]], seed: int = 0, per_kind: int = PER_KIND) -> Iterator[Mutant]:
    """Одни и те же мутанты при одном seed: замеры сравнимы между прогонами."""
    for kind, change in MUTATORS.items():
        order = sorted(claims, key=lambda c: c["id"])
        random.Random(f"{seed}:{kind}").shuffle(order)
        made = 0
        for claim in order:
            new = change(claim["text"])
            if new and new != claim["text"] and made < per_kind:
                made += 1
                yield Mutant(kind, claim["id"], new, source_of(claim))


# эти две порчи вставляют ровно те слова, которые ищет сверка кодом: она поймала бы их почти всегда, и замер соврал бы
CIRCULAR = frozenset({"negation_added", "overgeneralization"})


def measure(claims: Sequence[Mapping[str, Any]], check: Callable[[str, str], list[str]] = claim_flags, seed: int = 0) -> dict[str, Any]:
    """Доля порчи, которую видит сверка кодом. Портятся только утверждения без находок; оговорка убирается, только если она есть в цитате."""
    before = {c["id"]: check(c["text"], source_of(c)) for c in claims}
    clean = [c for c in claims if not before[c["id"]]]
    rows: dict[str, list[bool]] = {}
    for mutant in mutants(clean, seed):
        if mutant.kind in CIRCULAR or (mutant.kind == "lost_condition" and not HEDGE.search(mutant.quote)):
            continue
        rows.setdefault(mutant.kind, []).append(bool(check(mutant.text, mutant.quote)))
    kinds = {k: {"made": len(v), "caught": sum(v)} for k, v in rows.items()}
    made, caught = sum(k["made"] for k in kinds.values()), sum(k["caught"] for k in kinds.values())
    return {"seed": seed, "kinds": kinds, "made": made, "caught": caught, "recall": round(caught / made, 3) if made else None,
            "flagged_originals": len(claims) - len(clean), "originals": len(claims)}


__all__ = ["HEDGE", "MUTATORS", "OPPOSITES", "Mutant", "measure", "mutants"]
