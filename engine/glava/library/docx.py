"""DOCX -> страницы. Номера страниц — из разрывов Word. Что в текст перенести нельзя, называется."""

import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree

from glava.library import LibraryError
from glava.library.page import PICTURES, Page, shifted

MAX_XML_BYTES = 20 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
BREAK = "\f"  # явный разрыв страницы
SOFT_BREAK = "\v"  # разрыв, который Word запомнил при показе
WRAPPERS = {f"{W}{n}" for n in ("sdt", "sdtContent", "customXml", "ins", "moveTo", "smartTag")} | {f"{MC}AlternateContent", f"{MC}Choice"}
DROPPED = {f"{W}{n}" for n in ("del", "moveFrom", "pPr", "rPr", "sdtPr", "sdtEndPr", "tblPr", "trPr", "tcPr", "instrText", "delText")} | {f"{MC}Fallback"}
FORMULAS, TABLES = "формулы могли исказиться", "таблица сложная: ячейки могли сместиться"
NOTES = {"footnote": "footnotes.xml", "endnote": "endnotes.xml"}
Element = ElementTree.Element


def _parse(archive: zipfile.ZipFile, name: str) -> Element | None:
    if name not in archive.namelist():
        return None
    with archive.open(name) as source:
        raw = source.read(MAX_XML_BYTES + 1)
    # объявления сущностей в документах Word не бывает, а бомба из них съест память
    plain = raw.replace(b"\x00", b"")
    if len(raw) > MAX_XML_BYTES:
        raise LibraryError("документ слишком большой")
    if b"<!DOCTYPE" in plain or b"<!ENTITY" in plain:
        raise LibraryError("файл не похож на исправный DOCX")
    return ElementTree.fromstring(raw)


class _Reader:
    """Обход одного документа; reasons копятся для текущей страницы."""

    def __init__(self, notes: dict[str, dict[str, Element]]) -> None:
        self.notes = notes
        self.reasons: set[str] = set()
        self.pending: list[str] = []
        self.boxes: list[Element] = []

    def run_text(self, node: Element, way: str = "") -> str:
        if node.tag in DROPPED:
            return ""
        if node.tag == f"{W}r":
            look = node.find(f"{W}rPr")
            if look is not None and _is_on(look.find(f"{W}vanish")):
                self.reasons.add("скрытый текст документа пропущен")
                return ""
            if look is not None and (_is_on(look.find(f"{W}strike")) or _is_on(look.find(f"{W}dstrike"))):
                self.reasons.add("есть зачёркнутый текст")
            align = look.find(f"{W}vertAlign") if look is not None else None
            way = {"superscript": "up", "subscript": "down"}.get(align.get(f"{W}val") or "", "") if align is not None else ""
        if node.tag == f"{W}t":
            return shifted(node.text or "", way)
        if node.tag == f"{M}t":
            return node.text or ""
        if node.tag == f"{W}br":
            return BREAK if node.get(f"{W}type") == "page" else " "
        if node.tag in (f"{W}tab", f"{W}cr"):
            return " "
        if node.tag == f"{W}lastRenderedPageBreak":
            return SOFT_BREAK
        if node.tag == f"{W}noBreakHyphen":
            return "-"
        if node.tag == f"{W}softHyphen":
            return ""
        if node.tag == f"{W}sym":
            self.reasons.add("есть знаки особого шрифта: они не прочитаны")
            return "�"
        if node.tag in (f"{W}footnoteReference", f"{W}endnoteReference"):
            return self._note(node)
        if node.tag == f"{W}txbxContent":
            self.boxes.append(node)
            self.reasons.add("есть врезки: они поставлены после абзаца")
            return ""
        if node.tag == f"{M}oMath":
            self.reasons.add(FORMULAS)
        elif node.tag in (f"{W}object", f"{W}altChunk"):
            self.reasons.add("есть вставленный объект: его содержание не прочитано")
        elif node.tag in (f"{W}drawing", f"{W}pict"):
            self.reasons.add(PICTURES)
        return "".join(self.run_text(child, way) for child in node)

    def _note(self, node: Element) -> str:
        kind = node.tag.removeprefix(W).removesuffix("Reference")
        number = node.get(f"{W}id") or ""
        found = self.notes.get(kind, {}).get(number)
        if found is None:
            self.reasons.add("текст сноски не найден")
            return f"[сноска {number}]"
        text = " ".join(t for p in found.iter(f"{W}p") if (t := self.run_text(p).strip()))
        self.pending.append(f"[сноска {number}] {text}")
        return f"[сноска {number}]"

    def paragraph(self, node: Element) -> str:
        look = node.find(f"{W}pPr")
        text = self.run_text_of(node)
        if look is None:
            return text
        if look.find(f"{W}numPr") is not None:
            self.reasons.add("номера списка не сохранились")
            text = f"- {text}" if text.strip(" \f\v") else text
        style = look.find(f"{W}pStyle")
        level = re.fullmatch(r"(?:Heading|Заголовок)?\s*([1-6])", style.get(f"{W}val") or "") if style is not None else None
        if level and text.strip(" \f\v"):
            lead = re.match(r"[\f\v]*", text)
            start = lead.end() if lead else 0
            text = f"{text[:start]}{'#' * int(level.group(1))} {text[start:].strip()}"
        return text

    def run_text_of(self, node: Element) -> str:
        return "".join(self.run_text(child) for child in node)

    def table(self, node: Element) -> str:
        rows: list[list[str]] = []
        for row in _unwrapped(node, f"{W}tr"):
            cells: list[str] = []
            for cell in _unwrapped(row, f"{W}tc"):
                look = cell.find(f"{W}tcPr")
                span = look.find(f"{W}gridSpan") if look is not None else None
                merged = look.find(f"{W}vMerge") if look is not None else None
                if span is not None or merged is not None or cell.find(f".//{W}tbl") is not None:
                    self.reasons.add(TABLES)
                text = " ".join(t for p in cell.iter(f"{W}p") if (t := self.run_text_of(p)).strip(" "))
                if BREAK in text or SOFT_BREAK in text:
                    self.reasons.add("таблица идёт через разрыв страницы")
                cells.append(re.sub(r"[\f\v]+", " ", text).replace("|", "/").strip())
                cells += [""] * ((int(span.get(f"{W}val") or 1) if span is not None else 1) - 1)
            rows.append(cells)
        rows = [r for r in rows if any(r)]
        if not rows:
            return ""
        width = max(map(len, rows))
        lines = ["| " + " | ".join([*r, *[""] * (width - len(r))]) + " |" for r in rows]
        return "\n".join([lines[0], "|" + " --- |" * width, *lines[1:]])


def _is_on(mark: Element | None) -> bool:
    return mark is not None and mark.get(f"{W}val") not in ("0", "false", "off")


def _unwrapped(node: Element, tag: str) -> Iterator[Element]:
    for child in node:
        if child.tag == tag:
            yield child
        elif child.tag in WRAPPERS:
            yield from _unwrapped(child, tag)


def _blocks(node: Element) -> Iterator[Element]:
    for child in node:
        if child.tag in WRAPPERS:
            yield from _blocks(child)
        elif child.tag not in DROPPED:
            yield child


def _notes(archive: zipfile.ZipFile) -> dict[str, dict[str, Element]]:
    found: dict[str, dict[str, Element]] = {}
    for kind, name in NOTES.items():
        root = _parse(archive, f"word/{name}")
        if root is not None:
            found[kind] = {n.get(f"{W}id") or "": n for n in root.iter(f"{W}{kind}")}
    return found


class _Pages:
    def __init__(self, reader: _Reader) -> None:
        self.reader = reader
        self.done: list[tuple[list[str], set[str]]] = [([], set())]

    def flush_reasons(self) -> None:
        self.done[-1][1].update(self.reader.reasons)
        self.reader.reasons = set()

    def turn(self, is_soft: bool) -> None:
        """Запомненный Word разрыв идёт следом за явным: вдвоём они — одна новая страница."""
        if is_soft and not self.done[-1][0]:
            return
        self.flush_reasons()
        self.done.append(([], set()))

    def add(self, text: str) -> None:
        if text.strip():
            self.done[-1][0].append(re.sub(r"[ \t]+", " ", text).strip())

    def add_paragraph(self, text: str) -> None:
        for piece in re.split(r"([\f\v])", text):
            if piece in (BREAK, SOFT_BREAK):
                self.turn(piece == SOFT_BREAK)
            else:
                self.add(piece)
        for note in self.reader.pending:
            self.add(re.sub(r"[\f\v]+", " ", note))
        self.reader.pending = []


def _walk(body: Element, reader: _Reader, pages: _Pages) -> None:
    for node in _blocks(body):
        if node.tag == f"{W}p":
            look = node.find(f"{W}pPr")
            if look is not None and _is_on(look.find(f"{W}pageBreakBefore")):
                pages.turn(is_soft=True)
            pages.add_paragraph(reader.paragraph(node))
            boxes, reader.boxes = reader.boxes, []
            for box in boxes:
                _walk(box, reader, pages)
            section = look.find(f"{W}sectPr") if look is not None else None
            if section is not None:
                kind = section.find(f"{W}type")
                if kind is None or kind.get(f"{W}val") != "continuous":
                    pages.turn(is_soft=True)
        elif node.tag == f"{W}tbl":
            pages.add(reader.table(node))
            pages.add_paragraph("")
        elif node.tag not in (f"{W}sectPr", f"{W}bookmarkStart", f"{W}bookmarkEnd", f"{W}proofErr"):
            reader.run_text(node)
            reader.reasons.add("есть часть документа, которую прочитать не удалось")
    pages.flush_reasons()


def docx_texts(file: Path) -> list[tuple[str, tuple[str, ...]]]:
    """Тексты страниц и причины сомнений по порядку."""
    try:
        with zipfile.ZipFile(file) as archive:
            root, notes = _parse(archive, "word/document.xml"), _notes(archive)
    except (zipfile.BadZipFile, KeyError, OSError, NotImplementedError, EOFError, RuntimeError, zipfile.LargeZipFile, ElementTree.ParseError) as error:
        raise LibraryError("файл не похож на исправный DOCX") from error
    body = root.find(f"{W}body") if root is not None else None
    if body is None:
        raise LibraryError("файл не похож на исправный DOCX")
    reader = _Reader(notes)
    pages = _Pages(reader)
    _walk(body, reader, pages)
    return [("\n\n".join(parts), tuple(sorted(reasons))) for parts, reasons in pages.done]


__all__ = ["Page", "docx_texts"]
