"""Глава конвейера: откуда берётся текст и где лежат результаты."""

import hashlib
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glava.modules.library.api import (
    SAFE_ID,
    LibraryError,
    library_chapter,
    load_source,
    unsure_pages,
)
from glava.modules.metrics.api import Spent, append_metrics
from glava.modules.source_text.api import (
    Unit,
    is_english_source,
    mark_unsure,
    parse_units,
    read_pages,
)
from glava.shared.json_files import read, read_or
from glava.shared.paths import workspace

log = logging.getLogger("glava")


@dataclass(frozen=True)
class Chapter:
    chapter_id: str
    prefix: str
    title: str
    book: str
    domain: Path
    units: tuple[Unit, ...]
    source: str
    pdf: Path | None = None

    @property
    def is_english(self) -> bool:
        return is_english_source(self.units)

    @property
    def work(self) -> Path:
        return workspace() / "work" / self.chapter_id

    @property
    def errata_file(self) -> Path:
        return self.domain / "errata" / f"{self.chapter_id}.json"


def _pages(chapter_id: str, md: str, ranges: Sequence[Sequence[int]]) -> dict[int, str]:
    """Страницы главы. Пустая глава — ошибка до первого платного запроса, а пропавшая страница видна в журнале."""
    wanted = [(first, last) for first, last in ranges]
    pages = read_pages(md, wanted)
    if not any(text.strip() for text in pages.values()):
        raise LibraryError(f"глава {chapter_id}: на страницах {ranges} нет текста; проверьте pages и метки <!-- page N -->")
    lost = [n for first, last in wanted for n in range(first, last + 1) if n not in pages]
    if lost:
        log.warning("глава %s: в тексте нет страниц %s", chapter_id, ", ".join(map(str, lost)))
    return pages


def load_chapter(chapter_id: str) -> Chapter:
    registry = read(workspace() / "chapters.json")
    info = registry["chapters"].get(chapter_id)
    if info is None:
        # глава реестра главнее: загруженная книга не может её подменить
        own = library_chapter(workspace(), chapter_id)
        if own is None:
            raise LibraryError(f"главы {chapter_id} нет ни в chapters.json, ни в базе знаний")
        return load_library_chapter(chapter_id, own)
    # загруженные книги лежат в своей папке, файлы организаторов — в общей
    texts, scans = (info["root"], info["root"]) if info.get("root") else (os.environ.get("GLAVA_BOOKS", registry["root"]), os.environ.get("GLAVA_PDFS", registry["pdf_root"]))
    md = (workspace() / texts / info["file"]).read_text(encoding="utf-8-sig")
    units = parse_units(_pages(chapter_id, md, info["pages"]))
    return Chapter(chapter_id, info["prefix"], info["title"], info["book"], workspace() / "domain" / info["domain"], tuple(units), info["file"],
                   workspace() / scans / info["pdf"] if info.get("pdf") else None)


def load_library_chapter(chapter_id: str, info: Mapping[str, Any]) -> Chapter:
    """Глава из загруженной книги: текст и PDF лежат рядом в library/<источник>/."""
    source = load_source(workspace(), info["source"])
    if not source.text.exists():
        raise LibraryError("текст книги ещё не извлечён: выполните glava extract")
    pages = _pages(chapter_id, source.text.read_text(encoding="utf-8"), info["pages"])
    units = mark_unsure(parse_units(pages), unsure_pages(source))
    return Chapter(chapter_id, info["prefix"], info["title"], info["book"], workspace() / "domain" / info["domain"], tuple(units), source.original.name, source.pdf)


def layer_of(chapter_id: str) -> tuple[Path, dict[str, Any]]:
    """Слой главы по имени: этим командам не нужны ни md, ни PDF."""
    if not SAFE_ID.fullmatch(chapter_id):
        raise LibraryError("глава: недопустимое имя")
    work = workspace() / "work" / chapter_id
    if not (work / "layer.json").exists():
        raise LibraryError(f"слой главы {chapter_id} ещё не собран")
    return work, read(work / "layer.json")


def file_digest(path: Path) -> str:
    """По нему видно, о каком слое отчёт: время файла об этом не говорит."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def errata_of(chapter: Chapter) -> list[dict]:
    """Лист опечаток этапа errata и записи человека из <глава>.manual.json."""
    files = (chapter.errata_file, chapter.errata_file.with_suffix(".manual.json"))
    return [e for file in files for e in read_or(file, {"entries": []})["entries"]]


NOTES = (("glossary.md", "Словарь пакета (термин | определение | English)", 3), ("it_bridges.md", "ИТ-мосты пакета (понятие | аналогия | что передаёт | где ломается)", 4))
MAX_NOTES = {"glossary.md": 40, "it_bridges.md": 10}
STEM = 6


def pack_notes(chapter: Chapter) -> str:
    """Строки глоссария и ИТ-мостов, чьё понятие чаще всего встречается в главе: весь пакет в каждом запросе стоил бы лишних денег."""
    text = " ".join(u.text for u in chapter.units).casefold()
    blocks = ""
    for name, title, columns in NOTES:
        file = chapter.domain / name
        lines = file.read_text(encoding="utf-8").splitlines() if file.exists() else []
        rows = [[c.strip() for c in line.strip().strip("|").split("|")][:columns] for line in lines if line.startswith("|")]
        usable = [row for row in rows if len(row) == columns and len(row[0]) >= 2 and set(row[0]) - set("-: ")]
        counted = [(text.count(row[0].split()[0].casefold()[:STEM]), row) for row in usable]
        found = [row for count, row in sorted(counted, key=lambda x: -x[0])[:MAX_NOTES[name]] if count]
        blocks += f"\n\n# {title}\n" + "\n".join(" | ".join(row) for row in found) if found else ""
    return blocks


def context_of(chapter: Chapter) -> str:
    misconceptions = read(chapter.domain / "misconceptions.json")
    listed = "\n".join(f"{m['id']}: {m['text']}" for m in misconceptions)
    difficulty = (chapter.domain / "difficulty.md").read_text(encoding="utf-8")
    return f"# Глава\n{chapter.title}. {chapter.book}\n\n# Заблуждения новичков\n{listed}\n\n# {difficulty}{pack_notes(chapter)}"


def write_metrics(chapter: Chapter, stage: str, nodes: int, replies: Sequence[Spent], video_seconds: float = 0) -> None:
    append_metrics(chapter.chapter_id, stage, nodes, replies, video_seconds)
