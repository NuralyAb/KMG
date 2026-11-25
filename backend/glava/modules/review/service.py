"""Проверка чужих пакетов: готовые ответы модуля и запуск новой проверки."""

import logging
import secrets
from collections.abc import Mapping
from typing import Any, BinaryIO, get_args

from pydantic import ValidationError

from glava.modules.catalog.api import Repository, iso
from glava.modules.review.packages import discard, extract_package
from glava.modules.review.schemas import Remark, Review, Severity
from glava.modules.runs.api import RunManager, RunRecord
from glava.shared.http.errors import not_found
from glava.shared.json_store import rows

log = logging.getLogger("glava.http")
UPLOADS = "review_uploads"


def _remark(raw: Mapping[str, Any]) -> Remark | None:
    try:
        return Remark.model_validate(raw)
    except ValidationError:
        log.warning("замечание не по схеме пропущено")
        return None


def list_reviews(repository: Repository, manager: RunManager) -> list[Review]:
    """Новые сверху."""
    started = {r.args["package_id"]: r.chapter for r in reversed(manager.records()) if isinstance(r.args.get("package_id"), str)}
    chapters = {**repository.package_chapters(), **started}

    def review(package_id: str, created: float, data: Mapping[str, Any]) -> Review:
        remarks = tuple(r for raw in rows(data.get("remarks")) if (r := _remark(raw)))
        counts = {s: sum(r.severity == s for r in remarks) for s in get_args(Severity)}
        return Review(package_id=package_id, chapter=chapters.get(package_id), created_at=iso(created), remarks=remarks, counts=counts)

    return [review(*found) for found in sorted(repository.reviews(), key=lambda f: f[1], reverse=True)]


def get_review(repository: Repository, manager: RunManager, package_id: str) -> Review:
    found = next((r for r in list_reviews(repository, manager) if r.package_id == package_id), None)
    if found is None:
        raise not_found("Такой проверки нет")
    return found


def start_review(repository: Repository, manager: RunManager, chapter_id: str, source: BinaryIO) -> RunRecord:
    """Распаковывает пакет в новую папку и ставит проверку в очередь."""
    chapter = repository.chapter(chapter_id)
    manager.check_free(chapter.id)
    folder = repository.root / "work" / UPLOADS / secrets.token_hex(8)
    package = extract_package(source, folder)
    try:
        return manager.start("review", chapter.id, ("--package", str(folder)), {"package_id": package.package_id})
    except Exception:
        discard(folder)
        raise
