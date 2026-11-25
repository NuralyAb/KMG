"""Настройки сервера. Секретов здесь нет; всё меняется переменными среды GLAVA_*."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMAND = ("uv", "run", "glava")
DEFAULT_PORT = 8200
MEGABYTE = 1024 * 1024


class ConfigError(RuntimeError):
    """Неверная настройка: текст показывается пользователю."""


@dataclass(frozen=True)
class Settings:
    root: Path = DEFAULT_ROOT
    run_command: tuple[str, ...] = DEFAULT_COMMAND
    port: int = DEFAULT_PORT
    max_processes: int = 2
    max_body_bytes: int = 80 * MEGABYTE
    max_book_bytes: int = 400 * MEGABYTE
    allowed_origins: frozenset[str] = frozenset({"http://127.0.0.1:5190", "http://localhost:5190"})
    poll_seconds: float = 0.3


def _root(value: str | None) -> Path:
    root = Path(value).resolve() if value else DEFAULT_ROOT
    if not root.is_dir():
        raise ConfigError(f"GLAVA_ROOT: папки {root} нет")
    return root


def _command(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_COMMAND
    try:
        parts = json.loads(value)
    except json.JSONDecodeError as error:
        raise ConfigError('GLAVA_RUN_COMMAND: нужен список JSON, например ["uv", "run", "glava"]') from error
    if not isinstance(parts, list) or not parts or not all(isinstance(p, str) and p for p in parts):
        raise ConfigError("GLAVA_RUN_COMMAND: нужен непустой список строк")
    return tuple(parts)


def _port(value: str | None) -> int:
    if not value:
        return DEFAULT_PORT
    if not value.isdecimal() or not 0 < int(value) < 65536:
        raise ConfigError("GLAVA_PORT: нужно число от 1 до 65535")
    return int(value)


def settings_from_env(env: Mapping[str, str]) -> Settings:
    return Settings(root=_root(env.get("GLAVA_ROOT")), run_command=_command(env.get("GLAVA_RUN_COMMAND")), port=_port(env.get("GLAVA_PORT")))
