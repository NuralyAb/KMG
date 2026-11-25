"""Процесс сборки со всеми потомками. На Windows — в объекте задания: гибель сервера тоже останавливает сборку, которая тратит деньги."""

import logging
import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

if sys.platform == "win32":
    from glava.modules.runs.winjob import Job

log = logging.getLogger("glava.http")
KILL_TIMEOUT_S = 10
# переменные окружения самого сервера не должны менять окружение корня
DROPPED_ENV = frozenset({"VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT", "GLAVA_ADMIN_PASSWORD"})


def child_env(env: Mapping[str, str]) -> dict[str, str]:
    kept = {k: v for k, v in env.items() if k.upper() not in DROPPED_ENV}
    return {**kept, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}


class ProcessTree:
    def __init__(self, command: Sequence[str], cwd: Path, log_file: Path, env: Mapping[str, str] | None = None) -> None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("ab") as out:
            # список аргументов без оболочки: значения из запроса не могут стать командой
            self._process = subprocess.Popen(list(command), cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                             env=child_env(os.environ if env is None else env), start_new_session=sys.platform != "win32")
        self._job = self._join_job()

    def _join_job(self) -> "Job | None":
        if sys.platform != "win32":
            return None
        try:
            return Job.holding(self._process.pid)
        except OSError as error:
            log.warning("процесс %s без объекта задания: %s", self._process.pid, error)
            return None

    def wait(self) -> int:
        return self._process.wait()

    def kill(self) -> None:
        """Останавливает процесс вместе с потомками."""
        if sys.platform != "win32":
            _kill_group(self._process.pid)
        elif self._job is not None:
            self._job.terminate()
        else:
            _taskkill(self._process.pid)
        if self._process.poll() is None:
            self._process.kill()

    def close(self) -> None:
        """После выхода главного процесса добивает оставшихся потомков."""
        if self._job is not None:
            self._job.close()


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)  # type: ignore[attr-defined]
    except ProcessLookupError:
        log.info("процесс %s уже завершён", pid)


def _taskkill(pid: int) -> None:
    done = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=KILL_TIMEOUT_S, check=False)
    if done.returncode:
        log.warning("taskkill %s: код %s", pid, done.returncode)
