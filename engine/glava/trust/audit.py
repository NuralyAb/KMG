"""Бесплатная сверка утверждения со своей цитатой: числа, отрицания, направления, кванторы, оговорки, единицы.

Находка — повод посмотреть, а не приговор: пересказ бывает законным. Насколько проверки чутки, меряет mutate.
"""

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from glava.stages.blocks import BARE_REFERENCE, REFERENCE
from glava.stages.enrich import sentences
from glava.trust.entail import source_of
from glava.verify import DASHES, node_texts, numbers_in, unsupported_numbers

NEGATION = re.compile(r"\b(?:не|нет|ни|без|нельзя|невозможно)\b|\bотсутств\w*", re.IGNORECASE)
DOUBLE = re.compile(r"\bне\s+(?:только|менее|более)\b|\bни\b", re.IGNORECASE)
QUANTIFIER = re.compile(r"\b(?:всегда|никогда|вс[её]|все|всех|всеми|люб(?:ой|ая|ое|ые|ого|ых|ым|ую|ом)|только|лишь|исключительно|кажд\w+|обязательно|полностью)\b", re.IGNORECASE)
HEDGE = re.compile(
    r"\b(?:обычно|часто|иногда|редко|нередко|преимущественно|примерно|приблизительно|около|порядка|почти|возможно|вероятно|мож(?:ет|но|но)|могут|если|при условии|"
    r"как правило|в основном|в большинстве|в некоторых|в отдельных|в ряде|в общем случае|при прочих равных|чаще|кроме|за исключением|условно|практически|только при|лишь при)\b",
    re.IGNORECASE,
)
# пары противоположностей: слева рост и больше, справа падение и меньше
OPPOSITES = tuple((re.compile(a, re.IGNORECASE), re.compile(b, re.IGNORECASE)) for a, b in (
    (r"\b(?:увелич|возраст|повыш|раст[её]т|растут|рост)\w*", r"\b(?:уменьш|сниж|пониж|убыва|сокращ|пада[ею])\w*"),
    (r"\b(?:больш(?:е|ий|ая|ое|ие|их|им|ими|ей|ую)|выше|высок\w+|максим\w+|превыша\w+)\b|[>≥]|\\geq?\b", r"\b(?:меньш(?:е|ий|ая|ое|ие|их|им|ими|ей|ую)|ниже|низк\w+|миним\w+)\b|[<≤]|\\leq?\b"),
    (r"\b(?:положительн|прям(?:ая|ой|о) )\w*", r"\b(?:отрицательн|обратн(?:ая|ой|о) )\w*"),
    (r"\b(?:до|раньше|перед)\b(?=\s+(?:обсадк|бурен|измерен|вскрыт))", r"\b(?:после|позже)\b(?=\s+(?:обсадк|бурен|измерен|вскрыт))"),
))
UNIT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|‰|°C|°|МПа|кПа|Па|атм|Ом[·*\s]?м|мкм|мм|см|км|м|мД|г|кг|т|мин|сут|ч|с|К)(?:[²³]|\^\d)?(?![\w·/])")
MIN_TERM = 6
MAX_STEM_LOSS = 2


def _numbers(text: str) -> str:
    return BARE_REFERENCE.sub(" ", REFERENCE.sub(" ", text))


def _units(text: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for number, unit in UNIT.findall(text.translate(DASHES)):
        found.setdefault(number.replace(",", "."), set()).add(unit)
    return found


def claim_flags(text: str, quote: str) -> list[str]:
    """Коды расхождений утверждения с цитатой."""
    flags = []
    if unsupported_numbers(_numbers(text), quote):
        flags.append("number")
    quoted = _units(quote)
    quoted_units = set().union(*quoted.values()) if quoted else set()
    if any(not units & quoted.get(number, quoted_units) for number, units in _units(text).items() if quoted_units):
        flags.append("unit")
    said, heard = len(NEGATION.findall(text)), len(NEGATION.findall(quote))
    if bool(said) != bool(heard) or abs(said - heard) > 1 or (said < heard and not DOUBLE.search(quote)):
        flags.append("negation")
    for up, down in OPPOSITES:
        (text_up, text_down), (quote_up, quote_down) = ((len(up.findall(t)), len(down.findall(t))) for t in (text, quote))
        if (text_up < quote_up and text_down > quote_down) or (text_up > quote_up and text_down < quote_down):
            flags.append("direction")
            break
    if {q.casefold() for q in QUANTIFIER.findall(text)} and not QUANTIFIER.search(quote):
        flags.append("quantifier")
    if HEDGE.search(quote) and not HEDGE.search(text):
        flags.append("condition")
    return flags


def _stem(term: str) -> re.Pattern[str]:
    words = [re.escape(w[:-MAX_STEM_LOSS] if len(w) > MIN_TERM else w) + (r"\w*" if len(w) > MIN_TERM else "") for w in term.casefold().split()]
    return re.compile(r"\b" + r"\s+".join(words) + r"(?!\w)")


def early_terms(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Термин встречается в тексте раньше узла, где объяснён. Список terms_used составляет сама модель, поэтому ему не верим."""
    ordered = sorted(nodes, key=lambda n: n["order"])
    home: dict[str, tuple[int, str]] = {}
    for node in reversed(ordered):
        home |= {t.casefold(): (node["order"], node["id"]) for t in node["terms_introduced"] if len(t) >= MIN_TERM}
    texts = {n["id"]: " ".join(t for where, t in node_texts(n) if where.startswith("layers")).casefold() for n in ordered}
    found = []
    for term, (order, where) in sorted(home.items()):
        pattern = _stem(term)
        early = [n["id"] for n in ordered if n["order"] < order and pattern.search(texts[n["id"]])]
        if early:
            found.append({"term": term, "explained_in": where, "used_in": early})
    return found


def prose_numbers(node: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Фразы связного текста с числами, которых нет в утверждениях узла."""
    source = " ".join(f"{c['text']} {c['quote']}" for c in node["claims"]) + " " + " ".join(
        t for where, t in node_texts(node) if where.startswith(("worked_examples", "book_tasks")))
    allowed = numbers_in(source)
    rows = []
    for where, text in node_texts(node):
        if where.startswith("layers"):
            rows += [{"node_id": node["id"], "where": where, "text": s, "numbers": sorted(numbers_in(_numbers(s)) - allowed)} for s in sentences(text)]
    return [r for r in rows if r["numbers"]]


def audit_layer(layer: Mapping[str, Any]) -> dict[str, Any]:
    nodes = layer["nodes"]
    claims = [(n, c) for n in nodes for c in n["claims"]]
    flagged = [{"claim_id": c["id"], "node_id": n["id"], "text": c["text"], "quote": c["quote"], "page_pdf": c["page_pdf"], "flags": flags}
               for n, c in claims if (flags := claim_flags(c["text"], source_of(c)))]
    repeated = Counter(c["quote"] for _, c in claims)
    return {
        "chapter": layer["chapter"], "claims": len(claims), "flagged": flagged, "by_flag": dict(Counter(f for row in flagged for f in row["flags"])),
        "needs_scan": sum(c.get("needs_scan") is True for _, c in claims), "by_model": sum(c.get("by_model") is True for _, c in claims),
        "prose_numbers": [row for n in nodes for row in prose_numbers(n)], "early_terms": early_terms(nodes),
        "repeated_quotes": sum(n - 1 for n in repeated.values() if n > 1),
    }
