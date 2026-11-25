"""Безопасная распаковка чужого пакета: только package.json и картинки, без выхода из папки и zip-бомб."""

import json
import logging
import shutil
import stat
import zipfile
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from glava.shared.http.errors import ApiError
from glava.shared.http.settings import MEGABYTE
from glava.shared.identifiers import is_key_name, is_safe_id, safe_parts

log = logging.getLogger("glava.http")
IMAGES = frozenset({".png", ".jpg", ".jpeg"})
MANIFEST = "package.json"
ENCRYPTED = 0x1
CHUNK = 64 * 1024
RATIO_FROM_BYTES = MEGABYTE


@dataclass(frozen=True)
class Limits:
    entries: int = 1000
    file_bytes: int = 40 * MEGABYTE
    total_bytes: int = 300 * MEGABYTE
    ratio: int = 100


@dataclass(frozen=True)
class Package:
    package_id: str
    chapter: str | None
    folder: Path


@dataclass(frozen=True)
class _Entry:
    info: zipfile.ZipInfo
    parts: tuple[str, ...]


def _bad(message: str) -> ApiError:
    return ApiError(422, "bad_package", message)


def _bomb() -> ApiError:
    return ApiError(413, "too_large", "Архив распаковывается в слишком большой объём")


def _entry(info: zipfile.ZipInfo) -> _Entry:
    parts = safe_parts(info.filename)
    if parts is None:
        raise _bad("В архиве есть недопустимый путь к файлу")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise _bad("В архиве есть символическая ссылка")
    if info.flag_bits & ENCRYPTED:
        raise _bad("Архив защищён паролем")
    return _Entry(info, parts)


def _is_junk(parts: Sequence[str]) -> bool:
    return any(p.startswith(".") or p == "__MACOSX" for p in parts)


def _without_top(entries: Sequence[_Entry]) -> list[_Entry]:
    """Пакет может лежать в одной общей папке архива — она убирается."""
    if any(e.parts == (MANIFEST,) for e in entries):
        return list(entries)
    tops = {e.parts[0] for e in entries if len(e.parts) == 2 and e.parts[1] == MANIFEST}
    if len(tops) != 1:
        raise _bad("В архиве нет файла package.json")
    top = tops.pop()
    return [_Entry(e.info, e.parts[1:]) for e in entries if e.parts[0] == top and len(e.parts) > 1]


def _is_wanted(parts: Sequence[str]) -> bool:
    if "key" in parts[-1].lower():
        return False
    return tuple(parts) == (MANIFEST,) or PurePosixPath(parts[-1]).suffix.lower() in IMAGES


def _select(archive: zipfile.ZipFile, limits: Limits) -> list[_Entry]:
    infos = archive.infolist()
    if len(infos) > limits.entries:
        raise _bomb()
    entries = [_entry(i) for i in infos if not i.is_dir()]
    chosen = [e for e in _without_top([e for e in entries if not _is_junk(e.parts)]) if _is_wanted(e.parts)]
    names = ["/".join(e.parts).lower() for e in chosen]
    if len(set(names)) != len(names):
        raise _bad("В архиве два файла с одним именем")
    sizes = [(e.info.file_size, e.info.compress_size) for e in chosen]
    if sum(size for size, _ in sizes) > limits.total_bytes or any(size > limits.file_bytes for size, _ in sizes):
        raise _bomb()
    if any(size > RATIO_FROM_BYTES and size > packed * limits.ratio for size, packed in sizes):
        raise _bomb()
    return chosen


def _copy(archive: zipfile.ZipFile, entry: _Entry, target: Path, limit: int) -> int:
    """Пишет файл и считает настоящие байты: заголовку архива верить нельзя."""
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with archive.open(entry.info) as source, target.open("xb") as out:
        while chunk := source.read(CHUNK):
            size += len(chunk)
            if size > limit:
                raise _bomb()
            out.write(chunk)
    return size


def _frame_files(manifest: dict[str, Any]) -> list[str]:
    frames = manifest.get("frames", [])
    if not isinstance(frames, list):
        raise _bad("В package.json поле frames должно быть списком")
    files = [f.get("file") if isinstance(f, dict) else None for f in frames]
    if not all(isinstance(f, str) for f in files):
        raise _bad("В package.json у кадра не указан файл")
    return [str(f) for f in files]


def _check_manifest(folder: Path) -> Package:
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8-sig"))
    except (ValueError, RecursionError) as error:
        raise _bad("Файл package.json не читается как JSON") from error
    if not isinstance(manifest, dict):
        raise _bad("Файл package.json должен быть объектом")
    package_id = manifest.get("package_id")
    if not is_safe_id(package_id) or len(package_id) > 100 or is_key_name(package_id):
        raise _bad("package_id: только латинские буквы, цифры, точка, дефис и подчёркивание, без слова key")
    present = {p.relative_to(folder).as_posix().lower() for p in folder.rglob("*") if p.is_file()}
    lost = [f for f in _frame_files(manifest) if f.lower() not in present]
    if lost:
        raise _bad(f"В архиве нет кадров, названных в package.json: {len(lost)}")
    chapter = manifest.get("chapter")
    return Package(package_id, chapter if isinstance(chapter, str) else None, folder)


def _extract(source: BinaryIO, folder: Path, limits: Limits) -> Package:
    try:
        with zipfile.ZipFile(source) as archive:
            chosen = _select(archive, limits)
            folder.mkdir(parents=True)
            left = limits.total_bytes
            for entry in chosen:
                left -= _copy(archive, entry, folder.joinpath(*entry.parts), min(left, limits.file_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, UnicodeError) as error:
        raise _bad("Файл не похож на исправный zip-архив") from error
    return _check_manifest(folder)


def extract_package(source: BinaryIO, folder: Path, limits: Limits | None = None) -> Package:
    """Распаковывает пакет в новую папку; при любой ошибке папки не остаётся."""
    try:
        return _extract(source, folder, limits or Limits())
    except Exception:
        discard(folder)
        raise


def discard(folder: Path) -> None:
    if folder.exists():
        shutil.rmtree(folder, onexc=lambda _, path, error: log.warning("не удалось убрать %s: %s", Path(path).name, type(error).__name__))
