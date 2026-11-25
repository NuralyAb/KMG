"""Публикация курса: снимок, который видят ученики. Пересборка его не меняет, пока автор не опубликует курс заново."""

import hashlib
import json
import logging
import secrets
import shutil
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from glava.modules.catalog.api import Repository
from glava.modules.publishing.course_files import MEDIA_TYPES
from glava.modules.publishing.schemas import (
    CoursePart,
    CourseStep,
    LearnCourse,
    Publication,
    PublishCheck,
)
from glava.modules.runs.api import RunManager
from glava.shared.http.errors import ApiError, conflict, not_found
from glava.shared.identifiers import is_key_file, is_safe_id, safe_parts
from glava.shared.json_store import JsonStore, rows, write_json

log = logging.getLogger("glava.http")
START = "window.COURSE="
MAX_DATA_BYTES = 64 * 1024 * 1024


def _course_data(folder: Path) -> tuple[dict[str, Any], str]:
    """Данные курса из data.js — ровно то, что увидит ученик — и отпечаток файла."""
    try:
        raw = (folder / "data.js").read_bytes()
    except OSError:
        raise conflict("Курс ещё не собран") from None
    text = raw[:MAX_DATA_BYTES].decode("utf-8", "replace").strip()
    try:
        data = json.loads(text.removeprefix(START).rstrip(";"))
    except ValueError:
        raise conflict("Файл data.js курса не читается: пересоберите курс") from None
    if not text.startswith(START) or not isinstance(data, dict) or not rows(data.get("steps")):
        raise conflict("В курсе нет шагов: пересоберите курс")
    return data, hashlib.sha256(raw).hexdigest()


def _claims(nodes: list[dict[str, Any]]) -> dict[str, str]:
    return {str(c.get("id")): str(c.get("quote")) for n in nodes for c in rows(n.get("claims"))}


def _number(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


class Publications:
    def __init__(self, root: Path, repository: Repository, runs: RunManager, store: JsonStore | None = None) -> None:
        self.root = root / "published"
        self._repository = repository
        self._runs = runs
        self._store = store or JsonStore()
        self._lock = threading.RLock()

    # --- ученик ---

    def folder(self, course_id: str) -> Path:
        if not is_safe_id(course_id) or not self._meta(course_id):
            raise not_found("Такого курса нет")
        return self.root / course_id

    def _meta(self, course_id: str) -> dict[str, Any]:
        return self._store.read_object(self.root / f"{course_id}.json") if (self.root / course_id / "index.html").is_file() else {}

    def _course(self, course_id: str) -> LearnCourse | None:
        meta = self._meta(course_id)
        try:
            return LearnCourse.model_validate({k: meta.get(k) for k in LearnCourse.model_fields}) if meta else None
        except ValueError:
            log.warning("запись о публикации %s не по схеме", course_id)
            return None

    def courses(self) -> list[LearnCourse]:
        names = [p.stem for p in self.root.glob("*.json") if is_safe_id(p.stem) and not is_key_file(p.name)]
        found = [c for n in names if (c := self._course(n)) is not None]
        return sorted(found, key=lambda c: (c.title.casefold(), c.id))

    def course(self, course_id: str) -> LearnCourse:
        found = self._course(course_id) if is_safe_id(course_id) else None
        if found is None:
            raise not_found("Такого курса нет")
        return found

    def published_at(self, course_id: str) -> str | None:
        found = self._course(course_id)
        return found.published_at if found else None

    # --- автор ---

    def state(self, chapter_id: str) -> Publication:
        self._repository.chapter(chapter_id)
        problem, digest = None, ""
        try:
            data, digest = _course_data(self._repository.course_folder(chapter_id))
            problem = self._mismatch(chapter_id, data)
        except ApiError as error:
            problem = error.message
        meta = self._meta(chapter_id)
        return Publication(published_at=str(meta["published_at"]) if meta else None, is_current=bool(meta) and meta.get("data_sha256") == digest,
                           problem=problem, checks=() if problem else self._checks(chapter_id), accepted=tuple(map(str, meta.get("accepted") or ())))

    def _mismatch(self, chapter_id: str, data: Mapping[str, Any]) -> str | None:
        """Курс и слой сверяются по содержанию: время файлов меняет даже копирование папки."""
        if str(data.get("id")) != chapter_id:
            return "В папке лежит курс другой главы: пересоберите курс"
        if _claims(rows(data.get("steps"))) != _claims(self._repository.nodes(chapter_id)):
            return "Курс собран из другой версии слоя: пересоберите курс"
        return None

    def _checks(self, chapter_id: str) -> tuple[PublishCheck, ...]:
        """Что автор должен увидеть перед публикацией. Код и число вместе: согласие на три замечания не годится для десяти."""
        trust, found = self._repository.trust(chapter_id), []

        def add(code: str, count: int, text: str) -> None:
            if count:
                found.append(PublishCheck(code=f"{code}:{count}", text=text))

        issues = self._repository.issue_count(chapter_id)
        add("layer_issues", issues, f"Замечаний к слою: {issues}")
        if trust.audit is None or trust.audit_stale:
            add("no_audit", 1, "Сверки кодом этой версии слоя не было")
        else:
            flagged, scans = len(rows(trust.audit.get("flagged"))), _number(trust.audit.get("needs_scan"))
            add("flagged", flagged, f"Утверждений, которые расходятся с цитатой: {flagged}")
            add("needs_scan", scans, f"Утверждений, которые нужно сверить со сканом: {scans}")
        if trust.verify is None or trust.verify_stale:
            add("no_verify", 1, "Вторая модель эту версию слоя не проверяла")
        else:
            for code, text in (("contradicts", "Противоречит источнику"), ("no", "Нет в источнике"), ("unchecked", "Не проверено")):
                parts = [trust.verify.get(k) for k in ("claims", "prose")]
                count = sum(_number(p.get(code)) for p in parts if isinstance(p, dict))
                add(code, count, f"{text}, утверждений и фраз: {count}")
        return tuple(found)

    def publish(self, chapter_id: str, accepted: frozenset[str]) -> Publication:
        with self._lock:
            self._runs.check_free(chapter_id)
            state = self.state(chapter_id)
            if state.problem:
                raise conflict(state.problem)
            missing = [c.text for c in state.checks if c.code not in accepted]
            if missing:
                raise conflict("Замечания изменились, просмотрите их ещё раз: " + "; ".join(missing))
            draft = self.root / f".new_{secrets.token_hex(6)}"
            try:
                _snapshot(self._repository.course_folder(chapter_id), draft)
                data, digest = _course_data(draft)
                problem = self._mismatch(chapter_id, data)
                if problem:
                    raise conflict(problem)
                meta = {**_summary(chapter_id, data), "published_at": datetime.now(UTC).isoformat(timespec="seconds"), "data_sha256": digest,
                        "accepted": [c.text for c in state.checks]}
                self._swap(chapter_id, draft, meta)
            finally:
                shutil.rmtree(draft, ignore_errors=True)
        return self.state(chapter_id)

    def _swap(self, chapter_id: str, draft: Path, meta: Mapping[str, Any]) -> None:
        """Прежний снимок возвращается, если новый не удалось поставить."""
        target, old = self.root / chapter_id, self.root / f".old_{secrets.token_hex(6)}"
        had = target.exists()
        if had:
            target.rename(old)
        try:
            draft.rename(target)
            write_json(self.root / f"{chapter_id}.json", meta)
        except OSError:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            if had:
                old.rename(target)
            raise
        shutil.rmtree(old, ignore_errors=True)

    def unpublish(self, chapter_id: str) -> None:
        with self._lock:
            folder = self.folder(chapter_id)
            (self.root / f"{chapter_id}.json").unlink(missing_ok=True)
            shutil.rmtree(folder)


def _snapshot(source: Path, target: Path) -> None:
    """Только файлы, которые нужны странице курса: без ссылок, скрытых файлов и служебных json."""
    for file in sorted(source.rglob("*")):
        parts = file.relative_to(source).parts
        if any(p.startswith(".") or is_key_file(p) for p in parts) or safe_parts("/".join(parts)) is None:
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(source.resolve()) or not file.is_file():
            continue
        if file.suffix.lower() in MEDIA_TYPES and file.suffix.lower() != ".json":
            place = target.joinpath(*parts)
            place.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, place)
    if not (target / "index.html").is_file():
        raise conflict("Курс ещё не собран")


def _summary(chapter_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
    steps = rows(data.get("steps"))
    ready = {str(s.get("id")): CourseStep(id=str(s.get("id")), order=_number(s.get("order")), title=str(s.get("short_title") or s.get("title") or ""),
                                          minutes=_number(s.get("minutes"))) for s in steps}
    parts = [CoursePart(title=str(p.get("title") or ""), steps=tuple(ready[n] for n in p.get("nodes") or () if n in ready)) for p in rows(data.get("parts"))]
    course = LearnCourse(id=chapter_id, title=str(data.get("title") or chapter_id), book=str(data.get("book") or ""), steps=len(steps),
                         minutes=sum(s.minutes for s in ready.values()), tasks=sum(len(rows(s.get("tasks"))) for s in steps), parts=tuple(parts), published_at="")
    return course.model_dump()
