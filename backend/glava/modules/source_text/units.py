"""Глава md -> страницы -> единицы главы (абзац, рисунок, формула, таблица, задача, заголовок)."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from glava.modules.source_text.english import (
    Reader,
    running_lines,
    separate_headings,
)
from glava.shared.language import is_english

PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
FIGURE_BLOCK = re.compile(r"^━+\s*FORMAT")
CAPTION = re.compile(r"^\**(Рис(унок)?|Фиг|Fig(ure)?)\b\.?\s*\d", re.IGNORECASE)
TASK_HEADING = re.compile(r"^#*\s*\**(Задач[аи]|Упражнени[ея]|Problems?|Exercises?)\**\.?\s*$", re.IGNORECASE)
TASK_ITEM = re.compile(r"^\**\d{1,3}\.\**\s")
RULE = re.compile(r"^-{3,}$")
# подпись, которую распознаватель приклеил к концу абзаца: «…в интерв: Рис. 32. Определение…»
GLUED_CAPTION = re.compile(r"(?<=\S)[ \t]+((?:Рис\.|РИС\.|Рисунок)\s*\d+(?:\.\d+)*\.\s+[А-ЯЁ])")
PAGE_NUMBER = re.compile(r"^\d{1,4}$")


@dataclass(frozen=True)
class Unit:
    unit_id: str
    kind: str
    page_pdf: int
    text: str
    by_recogniser: bool = False
    needs_scan: bool = False
    skippable: bool = False

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


def _english_units(blocks: Mapping[int, list[tuple[str, bool]]]) -> list[Unit]:
    split = {page: separate_headings(blocks[page]) for page in sorted(blocks)}
    running, reader = running_lines(split), Reader()
    units: list[Unit] = []
    for page, found in split.items():
        for index, (text, in_figure) in enumerate(found):
            # колонтитул посреди списка литературы или задач раздела не меняет
            kind, skippable = ("heading" if text.startswith("#") else "paragraph", True) if (page, index) in running else reader.read(text, in_figure)
            units.append(Unit(f"p{page:03d}.{index + 1:02d}", kind, page, text, by_recogniser=in_figure, skippable=skippable))
    return units


def is_english_source(units: Iterable[Unit]) -> bool:
    """Описания рисунков распознаватель пишет по-русски и в английской книге, поэтому они не в счёт."""
    return is_english("\n".join(u.text for u in units if not u.by_recogniser))


def split_glued_captions(found: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """Подпись рисунка внутри абзаца — отдельный блок: иначе рисунок остаётся без подписи, а абзац — с чужим текстом."""
    out: list[tuple[str, bool]] = []
    for text, in_figure in found:
        match = None if in_figure or text.lstrip().startswith(("#", "|")) else GLUED_CAPTION.search(text)
        if match:
            out += [(text[:match.start()].strip(), False), (text[match.start(1):].strip(), False)]
        else:
            out.append((text, in_figure))
    return out


def page_furniture(blocks: Mapping[int, list[tuple[str, bool]]]) -> set[tuple[int, int]]:
    """Колонтитулы и номера страниц русской книги: (страница, порядок с нуля).

    Номер страницы стоит у края листа; колонтитул ищется по краям без номера, поэтому его находит и строка «© …» над номером.
    """
    found: set[tuple[int, int]] = set()
    edges: dict[int, list[tuple[str, bool]]] = {}
    places: dict[tuple[int, int], int] = {}
    for page, items in blocks.items():
        numbers = {i for i, (text, in_figure) in enumerate(items) if not in_figure and PAGE_NUMBER.match(text.strip()) and (i <= 1 or i >= len(items) - 2)}
        found |= {(page, i) for i in numbers}
        rest = [i for i in range(len(items)) if i not in numbers]
        ends = sorted({rest[0], rest[-1]}) if rest else []
        edges[page] = [items[i] for i in ends]
        places |= {(page, k): i for k, i in enumerate(ends)}
    running = {(page, places[(page, k)]) for page, k in running_lines(edges)}
    # заголовок «# Глава XXIII» совпадает с колонтитулом «ГЛАВА XXIII», но это заголовок главы
    return found | {(page, i) for page, i in running if not blocks[page][i][0].lstrip().startswith("#")}


def parse_units(pages: Mapping[int, str]) -> list[Unit]:
    """Единицы главы с устойчивыми id вида p095.03 (страница и порядок на ней). Колонтитулы и номера страниц можно пропустить в плане."""
    blocks = {page: _blocks(pages[page]) for page in pages}
    if is_english("\n".join(text for found in blocks.values() for text, in_figure in found if not in_figure)):
        return _english_units(blocks)
    blocks = {page: split_glued_captions(found) for page, found in blocks.items()}
    furniture = page_furniture(blocks)
    units: list[Unit] = []
    in_tasks = False
    for page in sorted(pages):
        for index, (text, in_figure) in enumerate(blocks[page], start=1):
            first = text.splitlines()[0].strip()
            if TASK_HEADING.match(first):
                in_tasks = True
            elif first.startswith("#"):
                in_tasks = False
            kind = _kind(text, in_figure, in_tasks)
            units.append(Unit(f"p{page:03d}.{index:02d}", kind, page, text, by_recogniser=in_figure, skippable=(page, index - 1) in furniture))
    return units


def mark_unsure(units: Iterable[Unit], pages: set[int]) -> list[Unit]:
    """Единицы страниц, текст которых читала модель или программа распознавания."""
    return [replace(u, needs_scan=True) if u.page_pdf in pages else u for u in units]
