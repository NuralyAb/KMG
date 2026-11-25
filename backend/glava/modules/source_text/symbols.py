"""Буква ϰ (пьезопроводность), которую распознаватель прочитал как π или k. Бесплатная проверка до слоя.

Правило работает только в главе, где ϰ уже встречается с временем (ϰt) — значит, глава пишет пьезопроводность этой буквой.
Настоящее π стоит в 2πkh, 4πk, √π, sin(πx), π²ϰt, π/2; подменённое — там, где по смыслу стоит ϰ: πt, r²/4πt, σ/π, π/ρ², «π = 0,57 r²/t».
"""

import re
from collections.abc import Iterable

from glava.modules.source_text.units import Unit

KAPPA = r"(?:\\varkappa|\\kappa|ϰ|κ)"
PI = r"(?:\\pi(?![A-Za-z])|π)"
KAPPA_WITH_TIME = re.compile(KAPPA + r"\s*_?\{?\s*[^}\s]{0,3}\}?\s*t(?![A-Za-z])")
MIN_KAPPA_TIME = 3
# π перед временем; деление на π; π над чем-то, кроме числа; π как самостоятельная величина
PI_RULES = (
    re.compile(PI + r"\s*t(?![A-Za-z])"),
    re.compile(r"/\s*" + PI + r"(?!\s*[\^\d])"),
    re.compile(PI + r"\s*/\s*(?![\d\s])"),
    re.compile(r"\$\s*" + PI + r"\s*\$|" + PI + r"\s*=\s*\d"),
)
K_FOR_KAPPA = re.compile(r"\\sqrt\{\s*k\s*t\s*\}")
WINDOW = 24
NOTE_PI = "ϰ (пьезопроводность) прочитана как π; правило, сверить по скану"
NOTE_K = "ϰ (пьезопроводность) прочитана как k; правило, сверить по скану"


def uses_kappa_notation(units: Iterable[Unit]) -> bool:
    return sum(len(KAPPA_WITH_TIME.findall(u.text)) for u in units) >= MIN_KAPPA_TIME


def _excerpt(text: str, start: int, end: int) -> tuple[int, int]:
    left, right = max(0, start - WINDOW), min(len(text), end + WINDOW)
    return left, right


def _entry(unit: Unit, start: int, end: int, wrong: str, right: str, note: str) -> dict:
    left, right_end = _excerpt(unit.text, start, end)
    md = unit.text[left:right_end].strip()
    fixed = (unit.text[left:start] + unit.text[start:end].replace(wrong, right, 1) + unit.text[end:right_end]).strip()
    return {"md": md, "scan": fixed, "kind": "recognition", "note": note, "page": unit.page_pdf, "unit_id": unit.unit_id, "by_rule": "kappa"}


def kappa_suspects(units: Iterable[Unit]) -> list[dict]:
    """Места, где по правилу вместо ϰ стоит π или k. Записи в формате листа опечаток; md — дословный кусок единицы."""
    units = [u for u in units if not u.by_recogniser]
    if not uses_kappa_notation(units):
        return []
    found: list[dict] = []
    for unit in units:
        spans: set[tuple[int, int]] = set()
        for rule in PI_RULES:
            for match in rule.finditer(unit.text):
                pi = re.search(PI, unit.text[match.start():match.end()])
                spans.add((match.start() + pi.start(), match.start() + pi.end()))
        for start, end in sorted(spans):
            wrong = unit.text[start:end]
            found.append(_entry(unit, start, end, wrong, "\\varkappa" if wrong.startswith("\\") else "ϰ", NOTE_PI))
        for match in K_FOR_KAPPA.finditer(unit.text):
            k = match.start() + match.group().index("k")
            found.append(_entry(unit, k, k + 1, "k", "\\varkappa ", NOTE_K))
    return found
