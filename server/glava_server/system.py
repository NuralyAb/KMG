"""Состояние окружения: модель, Claude Code, ffmpeg. Ключи и пути наружу не отдаются."""

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from glava_server.schemas import Health

DEFAULT_PROVIDER = "claude_code"
DEFAULT_MODEL = "sonnet"


def health(env: Mapping[str, str], which: Callable[[str], str | None] = shutil.which) -> Health:
    stated = env.get("CLAUDE_EXE") or env.get("CLAUDE_CODE_EXECPATH")
    claude_found = Path(stated).is_file() if stated else which("claude") is not None
    return Health(provider=env.get("LLM_PROVIDER") or DEFAULT_PROVIDER, model=env.get("LLM_MODEL") or DEFAULT_MODEL,
                  claude_found=claude_found, ffmpeg_found=which("ffmpeg") is not None)
