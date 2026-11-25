"""Глава md -> страницы -> единицы главы (абзац, рисунок, формула, таблица, задача, заголовок)."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
FIGURE_BLOCK = re.compile(r"^━+\s*FORMAT")
CAPTION = re.compile(r"^\**(Рис(унок)?|Фиг|Fig(ure)?)\b\.?\s*\d", re.IGNORECASE)
TASK_HEADING = re.compile(r"^#*\s*\**(Задач[аи]|Упражнени[ея]|Problems?|Exercises?)\**\.?\s*$", re.IGNORECASE)
TASK_ITEM = re.compile(r"^\**\d{1,3}\.\**\s")
RULE = re.compile(r"^-{3,}$")


@dataclass(frozen=True)
class Unit:
    unit_id: str
    kind: str
    page_pdf: int
    text: str
    by_recogniser: bool = False
    needs_scan: bool = False

    @property
    def excerpt(self) -> str:
        return " ".join(self.text.split()[:12])


def read_pages(md: str, ranges: Iterable[tuple[int, int]]) -> dict[int, str]:
    """Страницы md из запрошенных диапазонов (включительно)."""
    wanted = {n for first, last in ranges for n in range(first, last + 1)}
    parts = PAGE_MARK.split(md)
    return {int(n): body.strip("\n") for n, body in zip(parts[1::2], parts[2::2], strict=True) if int(n) in wanted}


def _blocks(page: str) -> list[tuple[str, bool]]:
    """Блоки страницы по пустым строкам; описание рисунка распознавателем держится одним блоком до линейки."""
    blocks: list[tuple[str, bool]] = []
    current: list[str] = []
    in_figure = False

    def flush() -> None:
        text = "\n".join(current).strip()
        if text:
            blocks.append((text, in_figure))
        current.clear()

    for line in page.splitlines():
        stripped = line.strip()
        if RULE.match(stripped):
            flush()
            in_figure = False
        elif FIGURE_BLOCK.match(stripped) and not in_figure:
            flush()
            in_figure = True
            current.append(line)
        elif not stripped and not in_figure:
            flush()
        else:
            current.append(line)
    flush()
    return blocks


def _kind(text: str, in_figure: bool, in_tasks: bool) -> str:
    first = text.lstrip().splitlines()[0].strip()
    if in_figure or CAPTION.match(first):
        return "figure"
    if TASK_HEADING.match(first) or first.startswith("#"):
        return "heading"
    if first.startswith("|"):
        return "table"
    if text.lstrip().startswith("$$"):
        return "formula"
    if in_tasks and TASK_ITEM.match(first):
        return "task"
    return "paragraph"


def parse_units(pages: Mapping[int, str]) -> list[Unit]:
    """Единицы главы с устойчивыми id вида p095.03 (страница и порядок на ней)."""
    units: list[Unit] = []
    in_tasks = False
    for page in sorted(pages):
        for index, (text, in_figure) in enumerate(_blocks(pages[page]), start=1):
            first = text.splitlines()[0].strip()
            if TASK_HEADING.match(first):
                in_tasks = True
            elif first.startswith("#"):
                in_tasks = False
            kind = _kind(text, in_figure, in_tasks)
            units.append(Unit(f"p{page:03d}.{index:02d}", kind, page, text, by_recogniser=in_figure))
    return units


def mark_unsure(units: Iterable[Unit], pages: set[int]) -> list[Unit]:
    """Единицы страниц, текст которых читала модель или программа распознавания."""
    return [replace(u, needs_scan=True) if u.page_pdf in pages else u for u in units]
