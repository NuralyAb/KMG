"""Проверки ролика: сценарий до озвучки, дорожка после неё."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from glava.modules.video.ffmpeg import measured, samples_16k
from glava.modules.video.timeline import Placed
from glava.modules.video.voices import Word
from glava.shared.evidence import unsupported_numbers

MAX_SAY_WORDS = 18
MAX_SCREEN_WORDS = 8
MIN_PAUSE, MAX_PAUSE = 1.0, 1.5
MIN_CAPTION_S, MAX_STILL_S = 1.5, 8.0
FIRST, LAST = "hook", "transfer"
# frame — фраза о самой картинке (масштаб, что где нарисовано): факта главы в ней нет
NOT_FACTS = {"hook", "prediction", "transfer", "frame"}
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


@dataclass(frozen=True)
class Heard:
    text: str
    words: tuple[Word, ...]


def recognise(audio: Path, model_name: str = "small") -> Heard:
    """Локальное распознавание; модель Whisper работает на этом компьютере."""
    import numpy
    from faster_whisper import WhisperModel

    # звук декодирует ffmpeg: так распознавание не зависит от версии PyAV
    sound = numpy.frombuffer(samples_16k(audio), numpy.int16).astype(numpy.float32) / 32768

    segments, _ = WhisperModel(model_name, device="cpu", compute_type="int8").transcribe(sound, language="ru", beam_size=5, word_timestamps=True)
    found = list(segments)
    return Heard(" ".join(s.text.strip() for s in found), tuple(Word(w.start, w.end, w.word) for s in found for w in s.words or []))


def sync_error(placed: Sequence[Placed], heard: Sequence[Word]) -> float | None:
    """Худшее из 95 % расхождений между словом на дорожке и временем, к которому привязана сцена; None — слов совпало мало."""
    planned = [(token, p.start + w.start) for p in placed for w in p.speech.words for token in _words(w.text)]
    actual = [(token, w.start) for w in heard for token in _words(w.text)]
    blocks = SequenceMatcher(None, [t for t, _ in planned], [t for t, _ in actual], autojunk=False).get_matching_blocks()
    gaps = sorted(abs(planned[b.a + k][1] - actual[b.b + k][1]) for b in blocks for k in range(b.size))
    return round(gaps[int(len(gaps) * 0.95)], 2) if len(gaps) * 2 >= len(planned) and gaps else None


def pace_problems(placed: Sequence[Placed], total: float) -> list[str]:
    """Подпись держится не меньше 1,5 с, шаг сцены — не дольше 8 с."""
    ends = [*(p.start for p in placed[1:]), total]
    shown = [(i, end - p.start, p) for i, (p, end) in enumerate(zip(placed, ends, strict=True), start=1)]
    short = [f"фраза {i}: подпись на экране {s:.1f} с, нужно {MIN_CAPTION_S}" for i, s, _ in shown if s < MIN_CAPTION_S]
    return short + [f"фраза {i}: {s:.0f} с без движения в сцене" for i, s, p in shown[:-1] if s > MAX_STILL_S and not p.beat["action"]]


def loudness(audio: Path) -> float:
    return measured(audio)[0]
