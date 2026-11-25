"""Очередь запусков: не больше двух процессов сразу и не больше одного незавершённого запуска на главу."""

import logging
import os
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from glava.modules.runs.process import ProcessTree
from glava.modules.runs.schemas import RunCommand, RunState
from glava.modules.runs.store import RunRecord, RunStore, now
from glava.shared.http.errors import ApiError, conflict, not_found
from glava.shared.identifiers import is_safe_id

log = logging.getLogger("glava.http")
STOP_TIMEOUT_S = 15


@dataclass(frozen=True)
class _Live:
    process: ProcessTree
    watcher: threading.Thread


class RunManager:
    def __init__(self, root: Path, command: Sequence[str], max_processes: int, env: Callable[[], Mapping[str, str]] = lambda: os.environ) -> None:
        self.store = RunStore(root / "work" / "runs")
        self._root = root
        self._command = tuple(command)
        self._max_processes = max_processes
        self._env = env
        self._lock = threading.RLock()
        self._records: dict[str, RunRecord] = {}
        self._waiting: list[tuple[str, tuple[str, ...]]] = []
        self._live: dict[str, _Live] = {}
        self._stopped_as: dict[str, RunState] = {}
        self._is_closed = False

    def open(self) -> None:
        """Читает историю. Процессов прошлого сервера уже нет, поэтому незавершённое помечается failed."""
        with self._lock:
            self._is_closed = False
            for record in self.store.load():
                self._records[record.id] = record
                if record.is_active:
                    self._update(record.id, state="failed", finished_at=now())

    def close(self) -> None:
        """Останавливает процессы: без сервера за ними некому следить, а они тратят деньги."""
        with self._lock:
            self._is_closed = True
            for run_id, _ in self._waiting:
                self._update(run_id, state="failed", finished_at=now())
            self._waiting = []
            live = list(self._live.items())
            self._stopped_as |= {run_id: "failed" for run_id, _ in live}
        for run_id, item in live:
            self._kill(run_id, item)

    # --- чтение ---

    def records(self) -> list[RunRecord]:
        with self._lock:
            return list(reversed(self._records.values()))

    def get(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._records.get(run_id) if is_safe_id(run_id) else None
        if record is None:
            raise not_found("Такого запуска нет")
        return record

    def active_by_chapter(self) -> dict[str, str]:
        return {r.chapter: r.id for r in self.records() if r.is_active}

    # --- действия ---

    def check_free(self, chapter: str, package_id: str | None = None) -> None:
        active = [r for r in self.records() if r.is_active]
        if any(r.chapter == chapter for r in active):
            raise conflict("По этой главе уже идёт запуск: дождитесь его или отмените")
        if package_id is not None and any(r.args.get("package_id") == package_id for r in active):
            raise conflict("Этот пакет уже проверяется")

    def start(self, command: RunCommand, chapter: str, options: Sequence[str] = (), args: dict[str, Any] | None = None) -> RunRecord:
        shown = dict(args or {})
        with self._lock:
            if self._is_closed:
                raise conflict("Сервер останавливается, новые запуски не принимаются")
            self.check_free(chapter, shown.get("package_id"))
            run_id = f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(4)}"
            record = RunRecord(run_id, command, chapter, shown, "queued", created_at=now())
            self._records[run_id] = record
            self.store.save(record)
            self._waiting = [*self._waiting, (run_id, (command, chapter, *options))]
            self._pump()
            return self._records[run_id]

    def cancel(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self.get(run_id)
            if not record.is_active:
                raise conflict("Запуск уже завершён")
            item = self._live.get(run_id)
            if item is None:
                self._waiting = [w for w in self._waiting if w[0] != run_id]
                return self._update(run_id, state="cancelled", finished_at=now())
            self._stopped_as = {**self._stopped_as, run_id: "cancelled"}
        self._kill(run_id, item)
        if self.get(run_id).is_active:
            raise ApiError(500, "not_stopped", "Не удалось остановить процесс, попробуйте ещё раз")
        return self.get(run_id)

    # --- внутреннее ---

    def _update(self, run_id: str, **changes: Any) -> RunRecord:
        record = replace(self._records[run_id], **changes)
        self._records[run_id] = record
        self.store.save(record)
        return record

    def _kill(self, run_id: str, item: _Live) -> None:
        try:
            item.process.kill()
        except OSError:
            log.exception("запуск %s: процесс не остановлен", run_id)
        item.watcher.join(STOP_TIMEOUT_S)

    def _pump(self) -> None:
        """Под замком: запускает ждущих, пока есть место."""
        while self._waiting and len(self._live) < self._max_processes and not self._is_closed:
            (run_id, arguments), *self._waiting = self._waiting
            self._launch(run_id, arguments)

    def _launch(self, run_id: str, arguments: Sequence[str]) -> None:
        try:
            process = ProcessTree([*self._command, *arguments], self._root, self.store.log_path(run_id), self._env())
        except OSError as error:
            log.error("запуск %s: %s", run_id, error)
            self.store.note(run_id, "Не удалось запустить процесс: команда не найдена или недоступна")
            self._update(run_id, state="failed", started_at=now(), finished_at=now())
            return
        watcher = threading.Thread(target=self._watch, args=(run_id, process), name=f"run-{run_id}", daemon=True)
        self._live[run_id] = _Live(process, watcher)
        self._update(run_id, state="running", started_at=now())
        watcher.start()

    def _watch(self, run_id: str, process: ProcessTree) -> None:
        code = process.wait()
        process.close()
        with self._lock:
            self._live.pop(run_id, None)
            stopped = self._stopped_as.pop(run_id, None)
            state: RunState = stopped or ("done" if code == 0 else "failed")
            self._update(run_id, state=state, finished_at=now(), exit_code=None if stopped else code)
            self._pump()
