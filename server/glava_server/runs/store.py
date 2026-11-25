"""Записи запусков и журналы в work/runs/: <id>.json и <id>.log."""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from glava_server.names import is_safe_id
from glava_server.schemas import Run, RunCommand, RunState

log = logging.getLogger("glava_server")
TAIL_LINES = 40
TAIL_BYTES = 64 * 1024
CHUNK_BYTES = 1024 * 1024
REPLACE_ATTEMPTS = 5


@dataclass(frozen=True)
class RunRecord:
    id: str
    command: RunCommand
    chapter: str
    args: dict[str, Any]
    state: RunState
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None

    @property
    def is_active(self) -> bool:
        return self.state in ("queued", "running")


RECORD = TypeAdapter(RunRecord)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def decode(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").rstrip("\r")


class RunStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def log_path(self, run_id: str) -> Path:
        return self.folder / f"{run_id}.log"

    def load(self) -> list[RunRecord]:
        """Все записи, старые сверху. Битая запись пропускается."""
        found = [r for p in self.folder.glob("*.json") if (r := self._read(p))]
        return sorted(found, key=lambda r: (r.created_at, r.id))

    def _read(self, path: Path) -> RunRecord | None:
        try:
            record = RECORD.validate_json(path.read_bytes())
        except (OSError, ValidationError):
            log.warning("запись запуска %s не прочитана", path.name)
            return None
        return record if is_safe_id(record.id) and record.id == path.stem else None

    def save(self, record: RunRecord) -> None:
        target = self.folder / f"{record.id}.json"
        draft = target.with_suffix(".tmp")
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            draft.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=1), encoding="utf-8")
            _replace(draft, target)
        except OSError:
            log.exception("запись запуска %s не сохранена", record.id)

    def note(self, run_id: str, line: str) -> None:
        """Строка сервера в журнал запуска."""
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with self.log_path(run_id).open("a", encoding="utf-8") as file:
                file.write(f"{line}\n")
        except OSError:
            log.exception("журнал запуска %s не записан", run_id)

    def read_from(self, run_id: str, offset: int) -> bytes:
        try:
            with self.log_path(run_id).open("rb") as file:
                file.seek(offset)
                return file.read(CHUNK_BYTES)
        except FileNotFoundError:
            return b""

    def tail(self, run_id: str) -> list[str]:
        try:
            with self.log_path(run_id).open("rb") as file:
                size = file.seek(0, os.SEEK_END)
                file.seek(max(0, size - TAIL_BYTES))
                raw = file.read()
        except FileNotFoundError:
            return []
        return [decode(line) for line in raw.removesuffix(b"\n").split(b"\n")][-TAIL_LINES:] if raw else []

    def view(self, record: RunRecord) -> Run:
        values = {k: v for k, v in asdict(record).items() if k != "created_at"}
        return Run(**values, log_tail=self.tail(record.id))


def _replace(draft: Path, target: Path) -> None:
    """На Windows антивирус может на миг держать файл."""
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(draft, target)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.05)
