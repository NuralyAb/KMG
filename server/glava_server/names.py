"""Проверка имён и относительных путей, пришедших снаружи."""

import re

SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
KEY_WORD = re.compile(r"(^|[^a-z])key([^a-z]|$)")
FORBIDDEN = re.compile(r'[<>:"|?*\\\x00-\x1f]')
DEVICES = frozenset({"con", "prn", "aux", "nul", *(f"com{n}" for n in range(10)), *(f"lpt{n}" for n in range(10))})


def is_safe_id(value: object) -> bool:
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None and _is_safe_part(value)


def is_key_name(stem: str) -> bool:
    return KEY_WORD.search(stem.lower()) is not None


def is_key_file(name: str) -> bool:
    """Файл ответов key.json и его варианты вроде ctrl_key.json: сервер их не читает и не отдаёт."""
    lowered = name.lower()
    return lowered.endswith(".json") and is_key_name(lowered.removesuffix(".json"))


def _is_safe_part(part: str) -> bool:
    if part in ("", ".", "..") or part[-1] in ". " or FORBIDDEN.search(part):
        return False
    return part.split(".")[0].strip().lower() not in DEVICES


def safe_parts(path: str) -> tuple[str, ...] | None:
    """Части относительного пути или None, если путь может вывести из папки или указать на особый файл Windows."""
    parts = tuple(path.split("/"))
    return parts if all(_is_safe_part(p) for p in parts) else None
