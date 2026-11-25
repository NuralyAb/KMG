"""Страница извлечённого текста и общие правила, когда ему нельзя верить."""

import re
from dataclasses import dataclass, field
from typing import Any

PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
MAX_PAGES = 2000
PICTURES = "есть рисунки: их содержание в текст не попало"
BAD_CHARS = re.compile(r"[�-\x00-\x08\x0b\x0e-\x1f]")
MIXED_WORD = re.compile(r"\b(?=\w*[а-яё])(?=\w*[a-z])[a-zа-яё]{3,}\b", re.IGNORECASE)
WORD = re.compile(r"\b[^\W\d_]{3,}\b")
UP = str.maketrans("0123456789+-−–()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁽⁾ⁿ")
DOWN = str.maketrans("0123456789+-−–()", "₀₁₂₃₄₅₆₇₈₉₊₋₋₋₍₎")
HEADING_LINE = re.compile(r"^(#{1,6}\s+\S.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Page:
    """state: text — надёжно, doubtful — сверить со сканом, scan — нужен распознаватель, empty — пусто."""

    page: int
    text: str
    state: str = "text"
    method: str = "text"
    reasons: tuple[str, ...] = field(default=())

    def record(self) -> dict[str, Any]:
        return {"page": self.page, "state": self.state, "method": self.method, "chars": len(self.text), "reasons": list(self.reasons)}


def shifted(text: str, way: str) -> str:
    """10 и поднятая 6 — это 10⁶, а не 106: без знака степени число изменилось бы."""
    if not way or not text.strip():
        return text
    left, core, right = text[:len(text) - len(text.lstrip())], text.strip(), text[len(text.rstrip()):]
    table = UP if way == "up" else DOWN
    small = core.translate(table)
    is_whole = all(ord(c) in table or c.isspace() for c in core)
    return f"{left}{small if is_whole else ('^' if way == 'up' else '_') + '{' + core + '}'}{right}"


def without_marks(text: str) -> str:
    """Метка страницы внутри чужого текста сдвинула бы номера страниц у цитат; вложенные метки снимаются до конца."""
    while PAGE_MARK.search(text):
        text = PAGE_MARK.sub(" ", text)
    return text


def separate_headings(text: str) -> str:
    """Строка-заголовок — отдельный блок: слитый с ней абзац считался бы заголовком и выпал бы из покрытия."""
    return re.sub(r"\n{3,}", "\n\n", HEADING_LINE.sub(r"\n\1\n", text)).strip("\n")


def text_reasons(text: str) -> list[str]:
    reasons = []
    if BAD_CHARS.search(text):
        reasons.append("нечитаемые знаки")
    words = WORD.findall(text)
    if len(words) >= 20 and len(MIXED_WORD.findall(text)) > len(words) * 0.02:
        reasons.append("в словах смешаны русские и латинские буквы")
    return reasons
