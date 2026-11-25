"""Проверки ролика: сценарий до озвучки, дорожка после неё."""

import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from glava.modules.video.timeline import Placed
from glava.shared.evidence import unsupported_numbers

MAX_SAY_WORDS = 18
MAX_SCREEN_WORDS = 8
MIN_PAUSE, MAX_PAUSE = 1.0, 1.5
FIRST, LAST = "hook", "transfer"
NOT_FACTS = {"hook", "prediction", "transfer"}
GREEK_OR_FORMULA = re.compile(r"[\u0370-\u03FF=<>≤≥≈∝^_]")
REQUIRED_LISTS = ("objects", "invariants", "assumptions", "exaggerations", "plaque")


def _beat_errors(beat: Mapping[str, Any], number: int, claims: Mapping[str, Mapping], source: str) -> list[str]:
    errors: list[str] = []
    if len(beat["say"].split()) > MAX_SAY_WORDS:
        errors.append(f"фраза {number}: длиннее {MAX_SAY_WORDS} слов")
    if len(beat["on_screen"].split()) > MAX_SCREEN_WORDS:
        errors.append(f"фраза {number}: на экране больше {MAX_SCREEN_WORDS} слов")
    if GREEK_OR_FORMULA.search(beat["on_screen"]):
        errors.append(f"фраза {number}: на экране формула или греческая буква")
    if beat["claim_id"] is not None and beat["claim_id"] not in claims:
        errors.append(f"фраза {number}: утверждения {beat['claim_id']} нет в узле")
    if beat["claim_id"] is None and beat["role"] not in NOT_FACTS and not beat["is_analogy"]:
        errors.append(f"фраза {number}: у факта нет утверждения")
    foreign = unsupported_numbers(f"{beat['say']} {beat['on_screen']}", source)
    return errors + ([f"фраза {number}: чисел нет в узле: {', '.join(sorted(foreign))}"] if foreign else [])


def script_errors(spec: Mapping[str, Any], node: Mapping[str, Any]) -> list[str]:
    claims = {c["id"]: c for c in node["claims"]}
    source = "\n".join(f"{c['text']} {c['quote']}" for c in node["claims"])
    beats = spec["beats"]
    errors = [e for i, b in enumerate(beats, start=1) for e in _beat_errors(b, i, claims, source)]
    roles = [b["role"] for b in beats]
    errors += ["первая фраза — крючок (hook) с вопросом"] if roles[0] != FIRST or "?" not in beats[0]["say"] else []
    errors += ["последняя фраза — вопрос на перенос (transfer)"] if roles[-1] != LAST or "?" not in beats[-1]["say"] else []
    guesses = [b for b in beats if b["role"] == "prediction"]
    if len(guesses) != 1 or not MIN_PAUSE <= float(guesses[0].get("pause_after") or 0) <= MAX_PAUSE:
        errors.append(f"нужна одна фраза prediction с паузой {MIN_PAUSE}–{MAX_PAUSE} с")
    errors += [f"поле {k} пустое" for k in REQUIRED_LISTS if not spec.get(k)]
    return errors


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower().replace("ё", "е").replace("\u0301", ""))


def word_error_rate(expected: str, heard: str) -> float:
    a, b = _words(expected), _words(heard)
    row = list(range(len(b) + 1))
    for i, word in enumerate(a, start=1):
        fresh = [i]
        for j, other in enumerate(b, start=1):
            fresh = [*fresh, min(row[j] + 1, fresh[-1] + 1, row[j - 1] + (word != other))]
        row = fresh
    return row[-1] / max(1, len(a))


def speech_rate(placed: Sequence[Placed]) -> float:
    words = sum(len(p.beat["say"].split()) for p in placed)
    return words / sum(p.end - p.start for p in placed) * 60


def recognise(audio: Path, model_name: str = "small") -> str:
    """Локальное распознавание; модель Whisper работает на этом компьютере."""
    from faster_whisper import WhisperModel

    segments, _ = WhisperModel(model_name, device="cpu", compute_type="int8").transcribe(str(audio), language="ru", beam_size=5)
    return " ".join(s.text.strip() for s in segments)


def loudness(audio: Path) -> float:
    done = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True)
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", done.stderr)
    if not found:
        raise RuntimeError("громкость не измерена")
    return float(found[-1])
