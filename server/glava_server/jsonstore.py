"""Чтение JSON конвейера. Конвейер может писать файл прямо сейчас, поэтому неполный файл — не ошибка."""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from glava_server.names import is_key_file

log = logging.getLogger("glava_server")
ATTEMPTS = 3
RETRY_DELAY_S = 0.05


class JsonStore:
    """Кэш по времени и размеру файла. Отданные данные вызывающий не меняет."""

    def __init__(self, retry_delay: float = RETRY_DELAY_S) -> None:
        self._retry_delay = retry_delay
        self._cache: dict[Path, tuple[tuple[int, int], Any]] = {}
        self._lock = threading.Lock()

    def read(self, path: Path) -> Any | None:
        """Данные файла; None, если файла нет. Для недописанного файла — последняя целая версия или None."""
        if is_key_file(path.name):
            return None
        with self._lock:
            cached = self._cache.get(path)
        for attempt in range(ATTEMPTS):
            try:
                stat = path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
                if cached and cached[0] == stamp:
                    return cached[1]
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return None
            except (OSError, ValueError):
                if attempt < ATTEMPTS - 1:
                    time.sleep(self._retry_delay)
                continue
            with self._lock:
                self._cache[path] = (stamp, data)
            return data
        log.warning("файл %s не читается целиком, показана прежняя версия: %s", path.name, "да" if cached else "её нет")
        return cached[1] if cached else None

    def read_object(self, path: Path) -> dict[str, Any]:
        data = self.read(path)
        return data if isinstance(data, dict) else {}

    def read_rows(self, path: Path, field: str) -> list[dict[str, Any]]:
        return rows(self.read_object(path).get(field))


def rows(value: Any) -> list[dict[str, Any]]:
    """Только словари: файлы пишет другая программа, чужую форму пропускаем."""
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []
