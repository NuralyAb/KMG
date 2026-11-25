"""Деление книги на главы и параграфы по заголовкам md. Без модели: человек подтверждает и правит границы."""

import re
from collections import Counter
from dataclasses import dataclass

PAGE = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
PART = re.compile(r"^(?:часть|part)\s+(?:[IVXLC]+|\d+)\b", re.IGNORECASE)
CHAPTER = re.compile(r"^(?:глава|chapter)\s+(?:[IVXLC]+|\d+)\b\.?", re.IGNORECASE)
PARAGRAPH = re.compile(r"^(?:§|section\b)\s*(?:[IVXLC]+[.\-])?\d+", re.IGNORECASE)
NUMBER = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(?=[^\W\d_])")
CONTENTS = re.compile(r"(?:\.{3,}|\s)\d+\s*$")
BARE = re.compile(r"^(?:глава|chapter)\s+(?:[IVXLC]+|\d+)\.?$", re.IGNORECASE)
PLAIN_RANK = 9
REPEATS = 3
MAX_TITLE = 200


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    level: int
    first: int
    last: int


@dataclass(frozen=True)
class _Mark:
    title: str
    rank: int
    page: int
    at_top: bool


def book_pages(md: str) -> dict[int, str]:
    parts = PAGE.split(md)
    return {int(n): body for n, body in zip(parts[1::2], parts[2::2], strict=True)}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`]|\\\(|\\\)|\$", "", text)).strip(" #")[:MAX_TITLE]


def rank_of(title: str) -> int:
    """Уровень по номеру, а не по числу решёток: распознаватель ставит их как попало."""
    if PART.match(title):
        return 0
    if CHAPTER.match(title):
        return 1
    if PARAGRAPH.match(title):
        return 2
    number = NUMBER.match(title)
    return 1 + number[1].count(".") if number else PLAIN_RANK


def _headings(pages: dict[int, str]) -> list[_Mark]:
    found: list[_Mark] = []
    for page in sorted(pages):
        is_top, after_bare = True, False
        for raw in pages[page].splitlines():
            line = raw.strip()
            if not line:
                continue
            match = HEADING.match(line)
            if not match:
                is_top = after_bare = False
                continue
            title = _clean(match[2])
            rank = rank_of(title)
            if after_bare and rank == PLAIN_RANK and found:
                # «Глава XXIII» и её название стоят двумя заголовками подряд
                found[-1] = _Mark(f"{found[-1].title.rstrip('.')}. {title}"[:MAX_TITLE], found[-1].rank, found[-1].page, found[-1].at_top)
                after_bare = False
                continue
            if title and not (CONTENTS.search(title) and "..." in title):
                found.append(_Mark(title, rank, page, is_top))
                after_bare = BARE.match(title) is not None
    return found


def _running(pages: dict[int, str]) -> list[_Mark]:
    """Колонтитул с номером на нескольких страницах подряд: раздел, у которого потерялся заголовок."""
    tops = {p: _clean(next((x for x in body.splitlines() if x.strip()), "")) for p, body in pages.items()}
    numbered = {p: t for p, t in tops.items() if rank_of(t) != PLAIN_RANK}
    common = {t for t, n in Counter(numbered.values()).items() if n >= REPEATS}
    marks, previous = [], None
    for page in sorted(numbered):
        title = numbered[page]
        if title in common and title != previous and all(m.title != title for m in marks):
            marks.append(_Mark(title, rank_of(title), page, at_top=True))
        previous = title
    return marks


def _key(title: str) -> str:
    number = NUMBER.match(title)
    return number[1] if number else re.sub(r"\W+", "", title).lower()[:40]


def split_book(md: str) -> list[Section]:
    pages = book_pages(md)
    if not pages:
        return []
    marks = _headings(pages)
    numbered = [m for m in marks if m.rank != PLAIN_RANK]
    running = _running(pages)
    numbered = sorted([*numbered, *running], key=lambda m: (m.page, m.rank)) if running else numbered
    chosen = numbered or [_Mark(m.title, 1, m.page, m.at_top) for m in marks]
    unique: list[_Mark] = []
    for mark in chosen:
        # номера вида 1.2 в книге не повторяются, а «§ 1» есть в каждой главе
        earlier = unique if NUMBER.match(mark.title) else unique[-1:]
        if all(_key(m.title) != _key(mark.title) for m in earlier):
            unique.append(mark)
    end, sections = max(pages), []
    for i, mark in enumerate(unique):
        after = next((m for m in unique[i + 1:] if m.rank <= mark.rank), None)
        last = end if after is None else after.page - 1 if after.at_top else after.page
        sections.append(Section(f"s{i + 1}", mark.title, mark.rank, mark.page, max(mark.page, last)))
    return sections


def merged_ranges(ranges: list[tuple[int, int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for first, last in sorted(ranges):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    return merged
