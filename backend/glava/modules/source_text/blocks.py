"""Блоки страницы шага, которые собирает код: «Цифры и условия» и «Таблицы книги»."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from glava.modules.source_text.units import Unit
from glava.shared.evidence import numbers_in, squeeze

REFERENCE = re.compile(
    r"(?:рис\w*|табл\w*|формул\w*|уравнени\w*|соотношени\w*|выражени\w*|пример\w*|задач\w*|стр\w*|§+|fig\w*|table\w*|eq\w*)\.?\s*\(?\d+(?:[.,]\d+)*\)?"
    r"(?:\s*(?:,|и|and|–|—|-)\s*\(?\d+\)?)*",
    re.IGNORECASE,
)
BARE_REFERENCE = re.compile(r"\(\s*\d{1,3}\s*\)|\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
SEPARATOR = re.compile(r"^:?-{3,}:?$")


def _measured_numbers(text: str) -> set[str]:
    return numbers_in(BARE_REFERENCE.sub(" ", REFERENCE.sub(" ", text)))


def number_blocks(node: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Утверждения с порогами, диапазонами и условиями; номера рисунков и формул не в счёт."""
    return [{"text": c["text"], "page": c["page_pdf"], "claim_id": c["id"]} for c in node["claims"] if _measured_numbers(c["text"])]


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().removeprefix("|").removesuffix("|").split("|")]


def _corrected(cell: str, entries: Sequence[Mapping[str, Any]]) -> str:
    for entry in entries:
        if entry["md"] in cell:
            cell = cell.replace(entry["md"], entry["scan"])
        elif squeeze(entry["md"]) == squeeze(cell):
            cell = entry["scan"]
    return cell


def _table(unit: Unit, errata: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    lines = [_cells(x) for x in unit.text.splitlines() if x.strip().startswith("|")]
    rows = [r for r in lines if any(r) and not all(SEPARATOR.match(c) for c in r if c)]
    if len(rows) < 2:
        return None
    entries = [e for e in errata if e["page"] == unit.page_pdf and e["kind"] == "recognition"]
    fixed = [[_corrected(c, entries) for c in r] for r in rows]
    corrections = [{"row": i - 1, "col": j, "from": rows[i][j], "to": fixed[i][j]} for i in range(len(rows)) for j in range(len(rows[i])) if rows[i][j] != fixed[i][j]]
    return {"title": f"Таблица книги, стр. {unit.page_pdf}", "page": unit.page_pdf, "unit_id": unit.unit_id, "header": fixed[0], "rows": fixed[1:], "corrections": corrections}


def book_tables(node: Mapping[str, Any], units: Sequence[Unit], errata: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Таблицы узла целиком; исправленные по скану ячейки перечислены в corrections."""
    own = [u for u in units if u.kind == "table" and u.unit_id in node["unit_ids"]]
    return [t for u in own if (t := _table(u, errata))]
