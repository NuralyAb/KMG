"""Книги: загрузка, оглавление, добавление главы в реестр. Модель не вызывается."""

import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

from glava.modules.books.splitter import Section, book_pages, merged_ranges, split_book
from glava.shared.http.errors import ApiError, invalid, not_found
from glava.shared.identifiers import is_key_name, is_safe_id

UPLOADED = "books"
MAX_MD = 20 * 1024 * 1024
MAX_PAGES = 120
LETTERS = dict(zip("абвгдезийклмнопрстуфхыэ", "abvgdeziiklmnoprstufhye", strict=True)) | {
    "ё": "e", "ж": "zh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ь": "", "ю": "yu", "я": "ya"}
_write = threading.Lock()


def slug(text: str) -> str:
    latin = "".join(LETTERS.get(c, c) for c in text.lower())
    return re.sub(r"[^a-z0-9]+", "_", latin).strip("_")[:40]


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    file: str
    uploaded: bool
    has_pdf: bool
    path: Path


class BookShelf:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _registry(self) -> dict[str, Any]:
        return json.loads((self.root / "chapters.json").read_text(encoding="utf-8"))

    def _given_folder(self, registry: dict[str, Any]) -> Path:
        return self.root / os.environ.get("GLAVA_BOOKS", str(registry.get("root") or UPLOADED))

    def books(self) -> list[Book]:
        registry = self._registry()
        known = {c.get("file"): c for c in registry["chapters"].values()}
        found: list[Book] = []
        for folder, uploaded in ((self.root / UPLOADED, True), (self._given_folder(registry), False)):
            for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
                book_id = slug(path.stem)
                if not book_id or any(b.id == book_id for b in found):
                    continue
                chapter = {} if uploaded else known.get(path.name, {})
                title = str(chapter.get("book") or "").split(", гл")[0].split(", §")[0] or self._title(path)
                found.append(Book(book_id, title, path.name, uploaded, path.with_suffix(".pdf").is_file() if uploaded else bool(chapter.get("pdf")), path))
        return found

    @staticmethod
    def _title(path: Path) -> str:
        with path.open(encoding="utf-8-sig", errors="replace") as file:
            head = file.read(2000)
        match = re.search(r"^#\s+(.+)$", head, re.MULTILINE)
        return match[1].strip()[:200] if match else path.stem

    def book(self, book_id: str) -> Book:
        found = next((b for b in self.books() if b.id == book_id), None)
        if found is None:
            raise not_found("Такой книги нет")
        return found

    def sections(self, book: Book) -> tuple[list[Section], list[int]]:
        md = book.path.read_text(encoding="utf-8-sig")
        return split_book(md), sorted(book_pages(md))

    def add(self, name: str, md: bytes, pdf: BinaryIO | None) -> Book:
        stem = slug(Path(name).stem)
        if not stem or is_key_name(stem) or not is_safe_id(stem) or not name.lower().endswith(".md"):
            raise invalid("Нужен файл .md с обычным именем")
        if len(md) > MAX_MD:
            raise ApiError(413, "too_large", "Текст книги больше 20 МБ")
        try:
            text = md.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise invalid("Файл .md должен быть в кодировке UTF-8") from error
        if not book_pages(text):
            raise invalid("В тексте нет меток страниц <!-- page N -->. Без них нельзя сверить цитаты")
        head = pdf.read(5) if pdf else b""
        if pdf and head != b"%PDF-":
            raise invalid("Второй файл должен быть PDF")
        folder = self.root / UPLOADED
        folder.mkdir(exist_ok=True)
        target = folder / f"{stem}.md"
        if any(b.id == stem for b in self.books()) and not (target.is_file() and target.read_bytes() == md):
            raise ApiError(409, "conflict", "Книга с таким именем уже есть. Переименуйте файл")
        target.write_bytes(md)
        if pdf:
            with target.with_suffix(".pdf").open("wb") as out:
                out.write(head)
                while chunk := pdf.read(1024 * 1024):
                    out.write(chunk)
        return self.book(stem)

    def domains(self) -> list[str]:
        folder = self.root / "domain"
        return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []

    def create_chapter(self, book_id: str, title: str, ranges: list[tuple[int, int]], domain: str) -> str:
        book = self.book(book_id)
        _, pages = self.sections(book)
        if not ranges or any(first > last for first, last in ranges):
            raise invalid("Укажите страницы: первая не больше последней")
        merged = merged_ranges(ranges)
        wanted = [p for first, last in merged for p in range(first, last + 1)]
        if len(wanted) > MAX_PAGES:
            raise invalid(f"Больше {MAX_PAGES} страниц: это дорого и не одна глава. Выберите меньше")
        missing = sorted(set(wanted) - set(pages))
        if missing:
            raise invalid(f"В книге нет страниц: {', '.join(map(str, missing[:10]))}")
        if not is_safe_id(domain) or not (self.root / "domain" / domain).is_dir():
            raise invalid("Такого доменного пакета нет")
        with _write:
            registry = self._registry()
            chapters = registry["chapters"]
            same = next((k for k, c in chapters.items() if c.get("file") == book.file and c.get("pages") == merged), None)
            if same:
                raise ApiError(409, "conflict", f"Такой отрезок уже есть: {chapters[same]['title']}")
            words = [w for w in book.id.split("_") if w not in ("train", "ctrl", "test")]
            prefix = next((w for w in words if re.fullmatch(r"[a-z][a-z0-9]*", w)), "book")
            base = f"{prefix}_{merged[0][0]}-{merged[-1][1]}"
            chapter_id, n = base, 2
            while chapter_id in chapters:
                chapter_id, n = f"{base}_{n}", n + 1
            # у каждой главы свой префикс узлов, иначе id двух глав одной книги совпадут
            taken = {c.get("prefix") for c in chapters.values()}
            node_prefix = prefix if prefix not in taken else slug(chapter_id)
            pdf = next((c.get("pdf") for c in chapters.values() if c.get("file") == book.file and c.get("pdf")), None)
            info = {"file": book.file, **({"root": UPLOADED} if book.uploaded else {}),
                    **({"pdf": book.path.with_suffix(".pdf").name} if book.uploaded and book.has_pdf else {"pdf": pdf} if pdf else {}),
                    "pages": merged, "prefix": node_prefix, "domain": domain, "title": title.strip(), "book": book.title}
            self._save({**registry, "chapters": {**chapters, chapter_id: info}})
        return chapter_id

    def _save(self, registry: dict[str, Any]) -> None:
        """Глава — одна строка, как в исходном реестре: правки видны в git построчно."""
        head = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in registry.items() if k != "chapters")
        rows = ",\n".join(f"    {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in registry["chapters"].items())
        text = "{\n" + (head + ",\n" if head else "") + '  "chapters": {\n' + rows + "\n  }\n}\n"
        temporary = self.root / "chapters.json.tmp"
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, self.root / "chapters.json")


def card(book: Book) -> dict[str, Any]:
    return {k: v for k, v in asdict(book).items() if k != "path"}
