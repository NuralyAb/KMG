"""База знаний: загруженные книги и главы из них. Файлы в library/, в git не попадают."""

import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import threading
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from pydantic import ValidationError

from glava_server.errors import ApiError, conflict, invalid, not_found
from glava_server.jsonstore import JsonStore, rows
from glava_server.names import is_safe_id
from glava_server.runs.manager import RunManager
from glava_server.runs.store import RunRecord
from glava_server.schemas import LibraryPage, NewChapter, Source, SourceDetail

log = logging.getLogger("glava_server")
KINDS = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".txt": "txt", ".png": "image", ".jpg": "image", ".jpeg": "image"}
SOURCE_ID = re.compile(r"src_[0-9a-f]{12}")
CHAPTER_ID = re.compile(r"lib_[0-9a-f]{8}")
PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
CHUNK = 1024 * 1024
NAME_CHARS = 160
MAX_CHAPTER_PAGES = 300
HEAD_BYTES = 1024


def _looks_like(kind: str, head: bytes, suffix: str) -> bool:
    if kind == "pdf":
        return b"%PDF-" in head
    if kind == "docx":
        return head.startswith(b"PK\x03\x04")
    if kind == "image":
        return head.startswith(b"\x89PNG\r\n\x1a\n" if suffix == ".png" else b"\xff\xd8\xff")
    return b"\x00" not in head


def _shown_name(name: str | None) -> str:
    """Имя только для показа: на диске файл всегда называется original.*."""
    last = re.split(r"[\\/]", name or "")[-1]
    return "".join(c for c in last if c.isprintable()).strip()[-NAME_CHARS:] or "файл"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
    try:
        draft.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        os.replace(draft, path)
    finally:
        draft.unlink(missing_ok=True)


class Library:
    def __init__(self, root: Path, runs: RunManager, store: JsonStore | None = None) -> None:
        self.root = root / "library"
        self._repo = root
        self._runs = runs
        self._store = store or JsonStore()
        self._lock = threading.RLock()

    # --- чтение ---

    def _folder(self, source_id: str) -> Path:
        folder = self.root / source_id
        if not SOURCE_ID.fullmatch(source_id) or not (folder / "source.json").is_file():
            raise not_found("Такого файла в базе знаний нет")
        return folder

    def _info(self, folder: Path) -> dict[str, Any]:
        return self._store.read_object(folder / "source.json")

    def _chapters(self) -> dict[str, Any]:
        file = self.root / "chapters.json"
        if not file.exists():
            return {}
        found = self._store.read_object(file).get("chapters")
        if not isinstance(found, dict):
            # запись поверх испорченного файла стёрла бы все главы
            raise ApiError(500, "broken_library", "Файл library/chapters.json повреждён: исправьте его или уберите")
        return found

    def _pages(self, folder: Path) -> list[LibraryPage]:
        rows_found = self._store.read_rows(folder / "pages.json", "pages")
        try:
            return [LibraryPage.model_validate(p) for p in rows_found]
        except ValidationError:
            log.warning("отчёт о страницах %s не по схеме: извлеките текст заново", folder.name)
            return []

    def _last_run(self, source_id: str) -> RunRecord | None:
        return next((r for r in self._runs.records() if r.chapter == source_id), None)

    def _source(self, folder: Path) -> Source:
        info, pages, run = self._info(folder), self._pages(folder), self._last_run(folder.name)
        if run is not None and run.is_active:
            state = "extracting"
        elif run is not None and run.state in ("failed", "cancelled"):
            state = "failed"
        else:
            state = "ready" if pages else "uploaded"
        return Source(
            id=folder.name, name=str(info.get("name") or folder.name), kind=str(info.get("kind") or ""), bytes=int(info.get("bytes") or 0),
            added_at=str(info.get("added_at") or ""), state=state, run=run.id if run else None, pages=len(pages),
            counts={s: sum(p.state == s for p in pages) for s in ("text", "doubtful", "scan", "empty")},
            chapters=tuple(c for c, i in self._chapters().items() if isinstance(i, dict) and i.get("source") == folder.name),
        )

    def sources(self) -> list[Source]:
        """Новые сверху."""
        folders = [f for f in self.root.glob("src_*") if SOURCE_ID.fullmatch(f.name) and (f / "source.json").is_file()]
        return sorted((self._source(f) for f in folders), key=lambda s: (s.added_at, s.id), reverse=True)

    def detail(self, source_id: str) -> SourceDetail:
        folder = self._folder(source_id)
        return SourceDetail(**dict(self._source(folder)), page_list=tuple(self._pages(folder)))

    def page_text(self, source_id: str, number: int) -> str:
        folder = self._folder(source_id)
        try:
            parts = PAGE_MARK.split((folder / "text.md").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise not_found("Текст книги ещё не извлечён") from None
        found = dict(zip(map(int, parts[1::2]), parts[2::2], strict=True))
        if number not in found:
            raise not_found("Такой страницы в книге нет")
        return found[number].strip()

    def page_image(self, source_id: str, number: int) -> Path:
        file = self._folder(source_id) / "preview" / f"p{number:05d}.png"
        if number < 1 or not file.is_file():
            raise not_found("Картинки этой страницы нет")
        return file

    def original(self, source_id: str) -> tuple[Path, str]:
        folder = self._folder(source_id)
        kind = str(self._info(folder).get("kind"))
        file = next((f for f in folder.glob("original.*") if f.suffix.lower() in KINDS), None)
        if file is None:
            raise not_found("Исходного файла нет на диске")
        return file, kind

    # --- действия ---

    def add(self, name: str | None, stream: BinaryIO, vision: bool) -> Source:
        suffix = PurePosixPath(_shown_name(name)).suffix.lower()
        kind = KINDS.get(suffix)
        if kind is None:
            raise ApiError(422, "bad_file", f"Такой файл не подходит. Можно: {', '.join(sorted(KINDS))}")
        source_id = f"src_{secrets.token_hex(6)}"
        draft = self.root / f".new_{source_id}"
        try:
            draft.mkdir(parents=True)
            digest, size = self._copy(stream, draft / f"original{suffix}")
            with (draft / f"original{suffix}").open("rb") as file:
                head = file.read(HEAD_BYTES)
            if not size:
                raise ApiError(422, "bad_file", "Файл пустой")
            if not _looks_like(kind, head, suffix):
                raise ApiError(422, "bad_file", "Содержимое файла не соответствует его расширению")
            if kind == "docx" and not zipfile.is_zipfile(draft / f"original{suffix}"):
                raise ApiError(422, "bad_file", "Файл не похож на исправный DOCX")
            write_json(draft / "source.json", {"id": source_id, "name": _shown_name(name), "file": f"original{suffix}", "kind": kind, "bytes": size,
                                               "sha256": digest, "added_at": datetime.now(UTC).isoformat(timespec="milliseconds")})
            with self._lock:
                if any(self._info(self.root / s.id).get("sha256") == digest for s in self.sources()):
                    raise conflict("Этот файл уже есть в базе знаний")
                draft.rename(self.root / source_id)
        except BaseException:
            shutil.rmtree(draft, ignore_errors=True)
            raise
        self._start(source_id, vision)
        return self._source(self.root / source_id)

    def _copy(self, stream: BinaryIO, target: Path) -> tuple[str, int]:
        digest, size = hashlib.sha256(), 0
        with target.open("xb") as out:
            while chunk := stream.read(CHUNK):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
        return digest.hexdigest(), size

    def _start(self, source_id: str, vision: bool) -> RunRecord:
        return self._runs.start("extract", source_id, ("--vision",) if vision else (), {"vision": vision})

    def extract(self, source_id: str, vision: bool) -> RunRecord:
        with self._lock:
            if self._source(self._folder(source_id)).chapters:
                raise conflict("Из этой книги уже сделаны главы: новое извлечение сдвинуло бы их цитаты. Сначала уберите главы")
            return self._start(source_id, vision)

    def add_chapter(self, source_id: str, request: NewChapter, domains: Sequence[str]) -> str:
        if request.domain not in domains:
            raise invalid("Такой предметной области нет")
        with self._lock:
            source = self._source(self._folder(source_id))
            if source.state != "ready":
                raise conflict("Дождитесь извлечения текста")
            _check_pages(request.pages, {p.page: p for p in self._pages(self.root / source_id)})
            chapter_id = f"lib_{secrets.token_hex(4)}"
            entry = {"source": source_id, "pages": [list(r) for r in request.pages], "prefix": chapter_id.replace("_", ""), "domain": request.domain,
                     "title": request.title.strip(), "book": (request.book or source.name).strip()}
            write_json(self.root / "chapters.json", {"chapters": {**self._chapters(), chapter_id: entry}})
        return chapter_id

    def remove_chapter(self, chapter_id: str) -> None:
        """Глава уходит из списка; собранные файлы в work/ и out/ остаются на диске."""
        with self._lock:
            chapters = self._chapters()
            if not CHAPTER_ID.fullmatch(chapter_id) or chapter_id not in chapters:
                raise not_found("Такой главы в базе знаний нет")
            self._runs.check_free(chapter_id)
            write_json(self.root / "chapters.json", {"chapters": {k: v for k, v in chapters.items() if k != chapter_id}})

    def remove(self, source_id: str) -> None:
        with self._lock:
            folder = self._folder(source_id)
            if self._source(folder).chapters:
                raise conflict("Из этой книги сделаны главы. Сначала уберите главы")
            self._runs.check_free(source_id)
            shutil.rmtree(folder)


def _check_pages(ranges: Sequence[tuple[int, int]], known: Mapping[int, LibraryPage]) -> None:
    chosen = [n for first, last in ranges for n in range(first, min(last, first + MAX_CHAPTER_PAGES) + 1)]
    if any(first > last for first, last in ranges) or len(set(chosen)) != len(chosen):
        raise invalid("Диапазоны страниц перепутаны или пересекаются")
    if len(chosen) > MAX_CHAPTER_PAGES:
        raise invalid(f"В главе может быть не больше {MAX_CHAPTER_PAGES} страниц")
    if any(n not in known for n in chosen):
        raise invalid("Таких страниц в книге нет")
    unread = [n for n in chosen if known[n].state == "scan"]
    if unread:
        raise invalid(f"Страницы без текста: {', '.join(map(str, unread[:10]))}. Прочитайте их моделью, иначе они пропадут из курса")
    if all(known[n].state == "empty" for n in chosen):
        raise invalid("На выбранных страницах нет текста")


def domain_names(root: Path) -> list[str]:
    """Предметные области, из которых можно собрать главу; общая первой."""
    needed = ("misconceptions.json", "difficulty.md", "styleguide.json", "physics_checklist.json")
    found = [d.name for d in (root / "domain").glob("*") if is_safe_id(d.name) and all((d / n).is_file() for n in needed)]
    return sorted(found, key=lambda n: (n != "general", n))


__all__ = ["Library", "domain_names", "rows", "write_json"]
