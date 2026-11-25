"""PDF -> страницы. Степени и индексы сохраняются; порядок, скрытый текст и слой распознавания, которым нельзя верить, называются."""

import re
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from glava.modules.library.page import MAX_PAGES, PICTURES, Page, shifted, text_reasons
from glava.modules.library.registry import LibraryError

MIN_PAGE_CHARS = 40
HEADING_SCALE, HEADING_CHARS = 1.15, 150
SCAN_SHARE, SMALL_SCALE = 0.5, 0.85
MANY_DRAWINGS = 20
TINY_PT = 3
MAX_GUESSES = 8
PARAGRAPH_CHARS, RUNNING_CHARS, COLUMN_CHARS, MIN_ROWS = 60, 90, 40, 3
EQUATION_NUMBER = re.compile(r"[(\[]?\d+(?:[.\-–]\d+)*[\w]?[)\]]")
MARGIN = 0.1
TRIVIAL_CONTENT = 50
MATH_FONT = re.compile(r"math|cmmi|cmsy|cmex|symbol|mtextra", re.IGNORECASE)
MATH_SIGN = re.compile(r"[∑∫√∂≤≥≈±∞∆∇×·÷αβγδεηθλμνρστφψωΔΣΩ]")
HYPHEN = re.compile(r"([^\W\d_]+)-$")
SOFT = "­"
WHITE = 0xFFFFFF


def _is_space(span: Mapping[str, Any]) -> bool:
    return not span["text"].strip()


def line_text(line: Mapping[str, Any]) -> str:
    """Строка вместе со степенями и индексами: мелкий символ выше строки — степень, ниже — индекс."""
    spans = line["spans"]
    size = max((s["size"] for s in spans if not _is_space(s)), default=0)
    base = [s["origin"][1] for s in spans if not _is_space(s) and s["size"] >= size * SMALL_SCALE]
    ground = statistics.median(base) if base else 0
    out = ""
    for span in spans:
        shift = span["origin"][1] - ground
        is_raised = bool(span["flags"] & 1) or (span["size"] < size * SMALL_SCALE and shift < -size * 0.12)
        is_lowered = span["size"] < size * SMALL_SCALE and shift > size * 0.05
        out += shifted(span["text"], "up" if is_raised else "down" if is_lowered else "") if not _is_space(span) else span["text"]
    return out


def _words(texts: Sequence[str]) -> set[str]:
    return {w.casefold() for t in texts for w in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", t)}


def joined(lines: Sequence[str], known: set[str], guesses: list[str] | None = None) -> str:
    """Строки абзаца одной строкой. Дефис в конце строки убирается, если слитное слово встречается в книге или дефисного в ней нет.

    Некоторые шрифты отдают обычный минус и дефис знаком мягкого переноса, поэтому он читается как дефис.
    Склейки наугад, когда книга не подсказала ни одной формы, копятся в guesses.
    """
    out = ""
    for line in (x.strip().replace("\u2010", "-").replace(SOFT, "-") for x in lines):
        head = re.match(r"[^\W\d_]+", line)
        tail = HYPHEN.search(out)
        if tail and head and head.group()[:1].islower():
            whole, hyphened = (tail.group(1) + head.group()).casefold(), f"{tail.group(1)}-{head.group()}".casefold()
            is_compound = "-" in out[:tail.start()][-1:] or (hyphened in known and whole not in known)
            if not is_compound and whole not in known and guesses is not None:
                guesses.append(whole)
            out = out + line if is_compound else out[:-1] + line
        else:
            out = f"{out} {line}" if out else line
    return out


def _length(block: Mapping[str, Any]) -> int:
    return sum(map(_line_length, block["lines"]))


def _is_running(block: Mapping[str, Any], page: Any) -> bool:
    """Колонтитул: одна короткая строка у края листа."""
    height = max(page.rect.height, 1)
    at_edge = block["bbox"][3] < page.rect.y0 + height * MARGIN or block["bbox"][1] > page.rect.y0 + height * (1 - MARGIN)
    rows = {round(x["bbox"][1]) for x in block["lines"]}
    return at_edge and len(rows) == 1 and _length(block) < RUNNING_CHARS


def _order_reasons(page: Any, blocks: Sequence[Mapping[str, Any]]) -> list[str]:
    """Колонки, таблицы без линеек, поворот и порядок рисования: текст мог собраться не так, как его читают."""
    main = [b for b in blocks if not _is_running(b, page)]
    wide = [b["bbox"] for b in main if _length(b) >= COLUMN_CHARS]
    beside = any((a[2] <= b[0] or b[2] <= a[0]) and min(a[3], b[3]) - max(a[1], b[1]) > 0.3 * min(a[3] - a[1], b[3] - b[1])
                 for i, a in enumerate(wide) for b in wide[i + 1:])
    reasons = ["текст стоит в несколько колонок: порядок мог сбиться"] if beside or _aligned_rows(main) >= MIN_ROWS else []
    boxes = [b["bbox"] for b in main if _length(b) >= PARAGRAPH_CHARS]
    if not beside and any(b[3] <= a[1] + 1 for a, b in zip(boxes, boxes[1:], strict=False)):
        reasons.append("абзацы записаны не сверху вниз: порядок мог сбиться")
    ways = {(round(x["dir"][0]), round(x["dir"][1])) for b in main for x in b["lines"] if _line_length(x) > 3}
    return reasons + (["есть повёрнутый текст: порядок мог сбиться"] if len(ways) > 1 else [])


def _aligned_rows(blocks: Sequence[Mapping[str, Any]]) -> int:
    """Сколько строк продолжаются правее с одного и того же места: так выглядят таблица без линеек и колонки. Номера формул и маркеры не в счёт."""
    lines = sorted((x for b in blocks for x in b["lines"] if _line_length(x)), key=lambda x: (round(x["bbox"][1]), x["bbox"][0]))
    starts: list[int] = []
    for left, right in zip(lines, lines[1:], strict=False):
        height = max(left["bbox"][3] - left["bbox"][1], 1)
        shown = "".join(s["text"] for s in right["spans"]).strip()
        if abs(left["bbox"][1] - right["bbox"][1]) < 2 and right["bbox"][0] - left["bbox"][2] > 1.5 * height and _line_length(left) > 2 and not EQUATION_NUMBER.fullmatch(shown):
            starts.append(round(right["bbox"][0] / 4))
    return max((starts.count(x) + starts.count(x + 1) for x in set(starts)), default=0)


def _line_length(line: Mapping[str, Any]) -> int:
    return sum(len(s["text"].strip()) for s in line["spans"])


def _hidden_reasons(page: Any) -> list[str]:
    trace = page.get_texttrace()
    if any(t["type"] == 3 for t in trace):
        return ["есть невидимый текст: обычно это слой распознавания поверх скана"]
    hidden = any(t.get("opacity", 1) == 0 or t["size"] < TINY_PT or (t["colorspace"] and all(c >= 0.99 for c in t["color"]) and len(t["color"]) in (1, 3)) for t in trace if t["chars"])
    return ["есть скрытый или нечитаемо мелкий текст"] if hidden else []


def pdf_page(page: Any, number: int, known: set[str]) -> Page:
    blocks = [b for b in page.get_text("dict")["blocks"] if b.get("lines") and any(not _is_space(s) for x in b["lines"] for s in x["spans"])]
    spans = [s for b in blocks for x in b["lines"] for s in x["spans"] if not _is_space(s)]
    body = statistics.median_low([s["size"] for s in spans for _ in range(max(1, len(s["text"]) // 5))]) if spans else 0
    parts, guesses = [], []
    for block in blocks:
        text = joined([t for t in map(line_text, block["lines"]) if t.strip()], known, guesses)
        sizes = [s["size"] for x in block["lines"] for s in x["spans"] if not _is_space(s)]
        is_heading = len(text) <= HEADING_CHARS and statistics.median_low(sizes) >= body * HEADING_SCALE
        parts.append(f"## {text}" if is_heading else text)
    text = "\n\n".join(parts)
    area = abs(page.rect)
    covered = sum(abs(page.rect & i["bbox"]) for i in page.get_image_info()) / area if area else 0
    drawings = len(page.get_cdrawings())
    if len(text) < MIN_PAGE_CHARS and (covered > SCAN_SHARE or (not text and (covered or drawings))):
        return Page(number, text, "scan", reasons=("текста нет, только изображение",))
    if not text:
        if len(page.read_contents() or b"") > TRIVIAL_CONTENT:
            return Page(number, "", "scan", reasons=("содержимое страницы не прочиталось",))
        return Page(number, "", "empty")
    reasons = [*text_reasons(text), *_hidden_reasons(page), *_order_reasons(page, blocks)]
    if covered > SCAN_SHARE:
        reasons.append("текст лежит поверх скана: это может быть слой распознавания")
    if any(MATH_FONT.search(s["font"]) for s in spans) or len(MATH_SIGN.findall(text)) > 3:
        reasons.append("формулы могли исказиться")
    if page.find_tables().tables:
        reasons.append("таблицы могли рассыпаться")
    notes = (PICTURES,) if (covered or drawings > MANY_DRAWINGS) and covered <= SCAN_SHARE else ()
    if guesses:
        notes = (*notes, f"переносы склеены по догадке: {', '.join(guesses[:MAX_GUESSES])}")
    return Page(number, text, "doubtful" if reasons else "text", reasons=(*reasons, *notes))


def pdf_pages(file: Path) -> list[Page]:
    import pymupdf

    with pymupdf.open(file, filetype="pdf") as document:
        if document.needs_pass:
            raise LibraryError("PDF защищён паролем")
        if document.page_count > MAX_PAGES:
            raise LibraryError(f"в PDF больше {MAX_PAGES} страниц")
        known = _words([page.get_text() for page in document])
        return [pdf_page(page, number, known) for number, page in enumerate(document, start=1)]
