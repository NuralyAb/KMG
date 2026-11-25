"""Файл -> страницы текста. Извлекает код; что код прочитал ненадёжно, он называет, а не прячет."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path

from glava.modules.library.docx import docx_texts
from glava.modules.library.page import (
    MAX_PAGES,
    PAGE_MARK,
    PICTURES,
    Page,
    separate_headings,
    text_reasons,
    without_marks,
)
from glava.modules.library.pdf import pdf_pages
from glava.modules.library.registry import LibraryError

KINDS = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".txt": "txt", ".png": "image", ".jpg": "image", ".jpeg": "image"}
VIRTUAL_PAGE_CHARS = 3000
OLD_ENCODINGS = ("cp1251", "cp866", "koi8-r", "mac_cyrillic")
COMMON = re.compile(r"[оеаинтслвр]")
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
MID_CAPITAL = re.compile(r"(?<=[а-яё])[А-ЯЁ]")
LOST_SHARE = 0.002
GUESSED = "кодировка не UTF-8, определена по догадке"


def to_md(pages: Iterable[Page]) -> str:
    return "\n\n".join(f"<!-- page {p.page} -->\n\n{separate_headings(without_marks(p.text))}" for p in pages) + "\n"


def image_pages(file: Path, target: Path) -> list[Page]:
    """Картинка становится PDF из одной страницы: дальше с ней работают как со сканом книги."""
    import pymupdf

    with pymupdf.open(file) as image:
        target.write_bytes(image.convert_to_pdf())
    return [Page(1, "", "scan", reasons=("текста нет, только изображение",))]


def docx_pages(file: Path) -> list[Page]:
    return _numbered(docx_texts(file))


def _numbered(found: Sequence[tuple[str, tuple[str, ...]]]) -> list[Page]:
    pages = []
    for number, (text, reasons) in enumerate(found, start=1):
        problems = (*reasons, *text_reasons(text))
        is_doubtful = any(x != PICTURES for x in problems)
        state = "doubtful" if is_doubtful else "text" if text.strip() else "empty"
        pages.append(Page(number, text, state, reasons=problems))
    return pages


def _guess(raw: bytes) -> str:
    """Из старых кодировок верна та, где частые русские буквы действительно часты и строчны."""
    def score(text: str) -> float:
        letters = len(CYRILLIC.findall(text))
        foreign = sum(ord(c) > 127 for c in text) - letters + len(MID_CAPITAL.findall(text))
        return (len(COMMON.findall(text)) - foreign) / letters if letters else -1.0

    return max((raw.decode(e, "replace") for e in OLD_ENCODINGS), key=score)


def decoded(raw: bytes) -> tuple[str, tuple[str, ...]]:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace"), ()
    try:
        return raw.decode("utf-8-sig"), ()
    except UnicodeDecodeError:
        text = raw.decode("utf-8-sig", "replace")
        if text.count("�") <= max(3, len(text) * LOST_SHARE):
            return text, ()
        return _guess(raw), (GUESSED,)


def _virtual(text: str) -> list[str]:
    """Текст без страниц режется по абзацам: иначе все цитаты указывали бы на страницу 1."""
    pages = [""]
    for block in re.split(r"\n\s*\n", text):
        if pages[-1] and len(pages[-1]) + len(block) > VIRTUAL_PAGE_CHARS:
            pages.append("")
        pages[-1] = f"{pages[-1]}\n\n{block}".strip("\n")
    return pages


def text_pages(file: Path) -> list[Page]:
    text, doubts = decoded(file.read_bytes())
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    marks = [int(n) for n in PAGE_MARK.findall(text)] if file.suffix.lower() == ".md" else []
    if marks:
        if marks[0] < 1 or any(b <= a for a, b in zip(marks, marks[1:], strict=False)):
            raise LibraryError("номера страниц в метках должны идти по возрастанию от 1")
        parts = PAGE_MARK.split(text)
        if parts[0].strip():
            raise LibraryError("до первой метки страницы есть текст: он потерялся бы")
        pages = _numbered([(body.strip("\n"), doubts) for body in parts[2::2]])
        return [replace(page, page=number) for page, number in zip(pages, marks, strict=True)]
    chunks = text.split("\f") if "\f" in text else _virtual(text)
    return _numbered([(c, doubts) for c in chunks])


def extract_pages(file: Path, kind: str, scan_pdf: Path) -> list[Page]:
    readers = {"pdf": pdf_pages, "docx": docx_pages, "md": text_pages, "txt": text_pages}
    try:
        pages = image_pages(file, scan_pdf) if kind == "image" else readers[kind](file)
    except LibraryError:
        raise
    except Exception as error:  # чужой файл может сломать любую библиотеку разбора
        raise LibraryError(f"файл не прочитался: {type(error).__name__}") from error
    if not pages or all(p.state == "empty" for p in pages):
        raise LibraryError("в файле не найдено ни текста, ни изображений")
    if len(pages) > MAX_PAGES:
        raise LibraryError(f"в файле больше {MAX_PAGES} страниц")
    return pages


__all__ = ["KINDS", "Page", "docx_pages", "extract_pages", "image_pages", "pdf_pages", "text_pages", "to_md"]
