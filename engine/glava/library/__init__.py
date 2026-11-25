"""База знаний: загруженные книги и главы из них. Всё лежит в library/ и в git не попадает."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
CHAPTER_PREFIX = "lib_"  # по этому началу .gitignore не пускает в git слои и курсы загруженных книг
SOURCE_FILE, PAGES_FILE, TEXT_FILE, CHAPTERS_FILE = "source.json", "pages.json", "text.md", "chapters.json"


class LibraryError(RuntimeError):
    """Ошибка с понятным человеку текстом."""


@dataclass(frozen=True)
class Source:
    source_id: str
    folder: Path
    original: Path
    kind: str

    @property
    def text(self) -> Path:
        return self.folder / TEXT_FILE

    @property
    def pages(self) -> Path:
        return self.folder / PAGES_FILE

    @property
    def pdf(self) -> Path | None:
        """PDF для сверки со сканом: сам файл или картинка, переведённая в PDF."""
        found = self.original if self.kind == "pdf" else self.folder / "scan.pdf"
        return found if found.exists() else None


def _safe(value: Any, what: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise LibraryError(f"{what}: недопустимое имя")
    return value


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LibraryError(f"нет файла {path.parent.name}/{path.name}") from None
    except ValueError:
        raise LibraryError(f"файл {path.parent.name}/{path.name} повреждён") from None


def load_source(root: Path, source_id: str) -> Source:
    folder = root / "library" / _safe(source_id, "источник")
    info = _read(folder / SOURCE_FILE)
    name = _safe(info.get("file"), "файл источника")
    return Source(source_id, folder, folder / name, _safe(info.get("kind"), "вид источника"))


def library_chapter(root: Path, chapter_id: str) -> Mapping[str, Any] | None:
    """Запись главы из базы знаний или None, если такой главы там нет."""
    registry = root / "library" / CHAPTERS_FILE
    if not chapter_id.startswith(CHAPTER_PREFIX) or not registry.exists():
        return None
    found = _read(registry)
    info = found.get("chapters", {}).get(chapter_id) if isinstance(found, dict) else None
    if not isinstance(info, dict):
        return None
    _safe(chapter_id, "глава")
    _safe(info.get("domain"), "предметная область")
    _safe(info.get("prefix"), "приставка главы")
    return info


def unsure_pages(source: Source) -> set[int]:
    """Страницы, текст которых прочитала модель или распознала программа: их утверждения сверяют со сканом."""
    if not source.pages.exists():
        raise LibraryError("нет отчёта о страницах: выполните glava extract ещё раз")
    return {p["page"] for p in _read(source.pages)["pages"] if p["state"] != "text"}
