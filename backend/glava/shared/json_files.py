"""Чтение и запись JSON этапов конвейера."""

import json
from pathlib import Path
from typing import Any


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_or(path: Path, default: Any) -> Any:
    return read(path) if path.exists() else default
