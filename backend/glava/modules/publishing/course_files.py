"""Файлы курса out/<глава>/: только внутри папки, без key.json и скрытых файлов, с постоянными типами."""

from pathlib import Path

from glava.shared.http.errors import ApiError, not_found
from glava.shared.identifiers import is_key_file, safe_parts

# типы заданы явно: на Windows mimetypes берёт их из реестра, и .js может прийти как text/plain
MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".woff2": "font/woff2", ".mp4": "video/mp4", ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".srt": "application/x-subrip; charset=utf-8", ".vtt": "text/vtt; charset=utf-8", ".txt": "text/plain; charset=utf-8",
}
DEFAULT_TYPE = "application/octet-stream"


def _missing() -> ApiError:
    return not_found("Такого файла в курсе нет")


def resolve_course_file(folder: Path, path: str) -> Path:
    parts = safe_parts(path)
    if parts is None or any(p.startswith(".") or is_key_file(p) for p in parts):
        raise _missing()
    root = folder.resolve()
    try:
        target = root.joinpath(*parts).resolve(strict=True)
    except (OSError, ValueError) as error:
        raise _missing() from error
    if not target.is_relative_to(root) or not target.is_file() or is_key_file(target.name):
        raise _missing()
    return target


def media_type(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), DEFAULT_TYPE)
