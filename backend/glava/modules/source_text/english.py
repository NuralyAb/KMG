"""Разбор английской главы: подписи, задачи, разобранные примеры, список литературы, колонтитулы. Русские главы сюда не попадают."""

import re
from collections import Counter
from collections.abc import Mapping, Sequence

Block = tuple[str, bool]

NUMBER = r"(?:[A-Z][.\-]?)?\d+(?:[.\-–]\d+)*"
SECTION = r"^#*\s*\**\s*(?:\d+(?:[.\-]\d+)*\.?\s+)?"
CAPTION = re.compile(rf"^#*\s*\**(?:Fig(?:ure)?s?|Plate|Exhibit|Photo)\b\.?\s*{NUMBER}", re.IGNORECASE)
# «Figure 3 shows that…» — абзац о рисунке, а не подпись под ним
MENTION = re.compile(
    rf"^\**(?:Fig(?:ure)?s?|Plate|Exhibit|Photo)\b\.?\s*{NUMBER}\s*(?:\(?[a-h]\)?)?,?\s+(?:shows?|illustrates?|presents?|gives?|depicts?|compares?|plots?|demonstrates?|"
    r"displays?|summari[sz]es?|describes?|indicates?|represents?|provides?|contains?|lists?|is|are|was|were|can|may|and|through|to|also|in|from|for|has|have)\b")
TABLE_CAPTION = re.compile(rf"^\**Table\s+{NUMBER}", re.IGNORECASE)
TASKS = re.compile(
    SECTION + r"(?:(?:chapter|section)\s+\d+\s+)?(?:(?:review|practice|homework|additional|suggested|study|discussion|self-test|end-of-chapter)\s+)?"
    r"(?:problems?|exercises?|questions?|assignments?)(?:\s+(?:and|for|to)\s+[\w ]+)?\s*\**\s*[:.]?\**$", re.IGNORECASE)
TASK = re.compile(rf"^#*\s*\**(?:Problem|Exercise|Question)\s+{NUMBER}", re.IGNORECASE)
TASK_ITEM = re.compile(rf"^\**\(?{NUMBER}[.):]?\**\s")
EXAMPLE = re.compile(rf"^#*\s*\**(?:(?:Worked\s+)?Example\s+{NUMBER}|Solution\b)", re.IGNORECASE)
REFERENCES = re.compile(
    SECTION + r"(?:(?:selected\s+)?references(?:\s+cited)?|bibliography|(?:further|suggested|recommended)\s+readings?|literature\s+cited|works\s+cited)\s*\**\s*[:.]?\**$",
    re.IGNORECASE)
FORMULA_START = ("$$", "\\[", "\\begin{")
RUNNING_PAGES = 3


def _first(text: str) -> str:
    return text.lstrip().splitlines()[0].strip()


def is_heading(first: str) -> bool:
    return first.startswith("#") or bool(TASKS.match(first) or REFERENCES.match(first))


def separate_headings(blocks: Sequence[Block]) -> list[Block]:
    """Заголовок отдельно от абзаца, который стоит под ним без пустой строки: иначе абзац выпал бы из покрытия."""
    found: list[Block] = []
    for text, in_figure in blocks:
        while not in_figure and "\n" in text and is_heading(_first(text)):
            heading, _, text = text.partition("\n")
            found.append((heading.strip(), False))
        found.append((text.strip(), in_figure))
    return [b for b in found if b[0]]


def running_lines(pages: Mapping[int, Sequence[Block]]) -> set[tuple[int, int]]:
    """Колонтитулы: первый или последний блок страницы, который с точностью до номера стоит ещё на двух страницах. (страница, порядок с нуля)"""
    edges = [(page, i, re.sub(r"[\W\d_]+", "", blocks[i][0]).casefold()) for page, blocks in pages.items() for i in {0, len(blocks) - 1} if blocks and not blocks[i][1]]
    counts = Counter(key for page, key in {(page, key) for page, _, key in edges if key})
    return {(page, i) for page, i, key in edges if counts[key] >= RUNNING_PAGES}


class Reader:
    """Вид блока зависит от раздела, в котором он стоит: задачи, пример, список литературы."""

    def __init__(self) -> None:
        self.in_tasks = self.in_references = self.after_example = False

    def read(self, text: str, in_figure: bool) -> tuple[str, bool]:
        """Вид единицы и можно ли её пропустить в плане."""
        first = _first(text)
        if in_figure or first.startswith("!["):
            return "figure", False
        if is_heading(first):
            self.in_references = bool(REFERENCES.match(first))
            self.in_tasks = bool(TASKS.match(first) or TASK.match(first))
            self.after_example = bool(EXAMPLE.match(first))
            return "heading", False
        after_example, self.after_example = self.after_example, False
        if self.in_references:
            return "paragraph", True
        if CAPTION.match(first) and not MENTION.match(first):
            return "figure", False
        if first.startswith(("|", "<table")) or (TABLE_CAPTION.match(first) and "\n|" in text):
            return "table", False
        if first.startswith(FORMULA_START):
            return "formula", False
        if TASK.match(first) or (self.in_tasks and (TASK_ITEM.match(first) or not EXAMPLE.match(first))):
            return "task", False
        return "worked_example" if after_example or EXAMPLE.match(first) else "paragraph", False
