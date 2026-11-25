"""Файлы конвейера: где лежат и как читаются. Путь строится только из проверенных имён реестра."""

import hashlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from glava_server.errors import ApiError, not_found
from glava_server.jsonstore import JsonStore, rows
from glava_server.metrics import read_metrics
from glava_server.names import is_key_file, is_safe_id
from glava_server.schemas import MetricRow, Trust

log = logging.getLogger("glava_server")
LIBRARY_CHAPTER = re.compile(r"lib_[0-9a-f]{8}")
STAGES = ("errata", "layer", "routing", "tasks", "illustrations", "course")


@dataclass(frozen=True)
class ChapterInfo:
    id: str
    title: str
    book: str
    domain: str
    pages: tuple[int, ...]


def _pages(ranges: Any) -> tuple[int, ...]:
    pairs = [r for r in ranges if isinstance(r, list) and len(r) == 2 and all(isinstance(n, int) for n in r)] if isinstance(ranges, list) else []
    return tuple(sorted({n for first, last in pairs for n in range(first, last + 1)}))


def _info(chapter_id: str, raw: Any) -> ChapterInfo | None:
    if not is_safe_id(chapter_id) or not isinstance(raw, dict) or not is_safe_id(raw.get("domain")):
        log.warning("запись реестра пропущена: недопустимое имя главы или домена")
        return None
    return ChapterInfo(chapter_id, str(raw.get("title") or chapter_id), str(raw.get("book") or ""), raw["domain"], _pages(raw.get("pages")))


def modified_at(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds")


class Repository:
    def __init__(self, root: Path, store: JsonStore | None = None) -> None:
        self.root = root
        self._store = store or JsonStore()

    # --- главы ---

    def chapters(self) -> list[ChapterInfo]:
        registry = self._store.read(self.root / "chapters.json")
        listed = registry.get("chapters") if isinstance(registry, dict) else None
        if not isinstance(listed, dict):
            raise ApiError(500, "no_registry", "Не удалось прочитать реестр глав chapters.json")
        own = self._store.read_object(self.root / "library" / "chapters.json").get("chapters")
        # глава базы знаний не может подменить главу реестра
        safe = {c: i for c, i in own.items() if LIBRARY_CHAPTER.fullmatch(c)} if isinstance(own, dict) else {}
        both = {**safe, **listed}
        names = [*listed, *(c for c in both if c not in listed)]
        return [info for chapter_id in names if (info := _info(chapter_id, both[chapter_id]))]

    def chapter(self, chapter_id: str) -> ChapterInfo:
        found = next((c for c in self.chapters() if c.id == chapter_id), None) if is_safe_id(chapter_id) else None
        if found is None:
            raise not_found("Такой главы нет в реестре")
        return found

    def _work(self, chapter_id: str, name: str) -> Path:
        return self.root / "work" / chapter_id / name

    def _errata_file(self, chapter: ChapterInfo) -> Path:
        return self.root / "domain" / chapter.domain / "errata" / f"{chapter.id}.json"

    def course_folder(self, chapter_id: str) -> Path:
        return self.root / "out" / chapter_id

    def has_course(self, chapter_id: str) -> bool:
        return (self.course_folder(chapter_id) / "index.html").is_file()

    def stage_times(self, chapter: ChapterInfo) -> Mapping[str, float | None]:
        files = {"errata": self._errata_file(chapter), "course": self.course_folder(chapter.id) / "index.html"}
        return {name: modified_at(files.get(name) or self._work(chapter.id, f"{name}.json")) for name in STAGES}

    # --- данные главы ---

    def nodes(self, chapter_id: str) -> list[dict[str, Any]]:
        found = self._store.read_rows(self._work(chapter_id, "layer.json"), "nodes")
        return [n for n in found if isinstance(n.get("id"), str)]

    def parts(self, chapter_id: str) -> list[dict[str, Any]]:
        return self._store.read_rows(self._work(chapter_id, "layer.json"), "parts")

    def coverage(self, chapter_id: str) -> list[dict[str, Any]]:
        return self._store.read_rows(self._work(chapter_id, "coverage.json"), "rows")

    def issue_count(self, chapter_id: str) -> int:
        issues = self._store.read_object(self._work(chapter_id, "layer_report.json")).get("issues")
        return sum(len(v) for v in issues.values() if isinstance(v, list)) if isinstance(issues, dict) else 0

    def trust(self, chapter_id: str) -> Trust:
        """Отчёт, сделанный по другому слою, устарел."""
        try:
            current = hashlib.sha256(self._work(chapter_id, "layer.json").read_bytes()).hexdigest()
        except OSError:
            current = ""

        def report(name: str) -> tuple[dict[str, Any] | None, bool]:
            found = self._store.read_object(self._work(chapter_id, name)) or None
            return found, found is not None and found.get("layer_sha256") != current

        audit, verify = report("audit.json"), report("trust.json")
        return Trust(audit=audit[0], audit_stale=audit[1], verify=verify[0], verify_stale=verify[1])

    def routes(self, chapter_id: str) -> list[dict[str, Any]]:
        return self._store.read_rows(self._work(chapter_id, "routing.json"), "routes")

    def tasks(self, chapter_id: str) -> list[dict[str, Any]]:
        return self._store.read_rows(self._work(chapter_id, "tasks.json"), "tasks")

    def illustrations(self, chapter_id: str) -> list[dict[str, Any]]:
        return self._store.read_rows(self._work(chapter_id, "illustrations.json"), "illustrations")

    def errata(self, chapter_id: str) -> list[dict[str, Any]]:
        return self._store.read_rows(self._errata_file(self.chapter(chapter_id)), "entries")

    def passports(self, chapter_id: str) -> list[tuple[str, dict[str, Any]]]:
        """Паспорта готовых роликов: (имя ролика, паспорт). Ролик без файла mp4 ещё не собран."""
        folder = self.course_folder(chapter_id) / "videos"
        names = sorted(p.name.removesuffix(".passport.json") for p in folder.glob("*.passport.json"))
        ready = [n for n in names if is_safe_id(n) and (folder / f"{n}.mp4").is_file()]
        return [(n, passport) for n in ready if (passport := self._store.read_object(folder / f"{n}.passport.json"))]

    def has_subtitles(self, chapter_id: str, video: str) -> bool:
        return (self.course_folder(chapter_id) / "videos" / f"{video}.srt").is_file()

    def has_video_template(self, domain: str, name: str) -> bool:
        return is_safe_id(name) and (self.root / "domain" / domain / "video" / f"{name}.py").is_file()

    # --- общее ---

    def metrics(self) -> list[MetricRow]:
        return read_metrics(self.root / "metrics.csv")

    def reviews(self) -> list[tuple[str, float, dict[str, Any]]]:
        """Ответы модуля проверки: (пакет, время, данные)."""
        files = [p for p in (self.root / "out" / "review").glob("*.json") if is_safe_id(p.stem) and not is_key_file(p.name)]
        found = [(p.stem, modified_at(p), self._store.read(p)) for p in files]
        return [(name, time, data) for name, time, data in found if time is not None and isinstance(data, dict)]

    def package_chapters(self) -> dict[str, str]:
        """Глава каждого проверенного пакета по package.json в рабочих копиях."""
        packages = [self._store.read_object(p) for folder in ("review_uploads", "review")
                    for p in sorted((self.root / "work" / folder).glob("*/package.json"))]
        return {p["package_id"]: p["chapter"] for p in packages if isinstance(p.get("package_id"), str) and isinstance(p.get("chapter"), str)}


__all__ = ["STAGES", "ChapterInfo", "Repository", "iso", "modified_at", "rows"]
