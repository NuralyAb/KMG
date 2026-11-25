"""Озвучка фраз: произношение по словарю, кэш готовых фраз, потолок знаков платного голоса, запасной голос на весь ролик."""

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from glava.modules.video.voices import (
    ElevenLabs,
    SpeechFailed,
    Voice,
    VoiceNotConfigured,
    Word,
)

log = logging.getLogger("glava")
TAIL = 0.15


@dataclass(frozen=True)
class Speech:
    path: Path
    duration: float
    words: tuple[Word, ...]


def spoken(text: str, abbreviations: Mapping[str, str], stresses: Mapping[str, str]) -> str:
    """Текст для голоса: аббревиатуры по словарю произношений, ударения знаком U+0301."""
    for short in sorted(abbreviations, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(short)}(?!\w)", abbreviations[short], text)

    def stress(match: re.Match[str]) -> str:
        word = match.group()
        marked = stresses.get(word.lower())
        if not marked:
            return word
        return marked[0].upper() + marked[1:] if word[0].isupper() else marked

    return re.sub(r"\w+", stress, text)


def dictionaries(pronunciation: str) -> tuple[dict[str, str], dict[str, str]]:
    """Таблицы «пишется — читается» и «слово — с ударением» из pronunciation.md доменного пакета."""
    short: dict[str, str] = {}
    stress: dict[str, str] = {}
    for line in pronunciation.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|") or len(cells) < 2 or set(cells[0]) <= {"-", " "}:
            continue
        if len(cells) >= 3 and cells[0] != "Пишется":
            keys, values = [k.strip() for k in cells[0].split(",")], [v.strip() for v in cells[1].split(",")]
            if len(keys) == len(values):
                short = {**short, **dict(zip(keys, values, strict=True))}
        elif len(cells) == 2 and "́" in cells[1]:
            stress = {**stress, cells[0].lower(): cells[1]}
    return short, stress


def _cached(text: str, folder: Path, voice: Voice) -> tuple[Path, Path]:
    key = hashlib.sha256(f"{voice.key}|{text}".encode()).hexdigest()[:24]
    return folder / f"{key}.mp3", folder / f"{key}.json"


def say(text: str, folder: Path, voice: Voice) -> Speech:
    text = voice.prepare(text)
    audio_path, words_path = _cached(text, folder, voice)
    if not (words_path.exists() and audio_path.exists()):
        folder.mkdir(parents=True, exist_ok=True)
        audio, words = voice.speak(text)
        audio_path.write_bytes(audio)
        words_path.write_text(json.dumps([[w.start, w.end, w.text] for w in words], ensure_ascii=False), encoding="utf-8")
    words = tuple(Word(*w) for w in json.loads(words_path.read_text(encoding="utf-8")))
    return Speech(audio_path, words[-1].end + TAIL, words)


def unspoken_chars(texts: Sequence[str], folder: Path, voice: Voice) -> int:
    """Сколько знаков придётся озвучить заново: готовые фразы бесплатны."""
    ready = [voice.prepare(t) for t in texts]
    return sum(len(t) for t in dict.fromkeys(ready) if not _cached(t, folder, voice)[1].exists())


@dataclass(frozen=True)
class Voiced:
    speeches: tuple[Speech, ...]
    voice: Voice
    paid_chars: int


def _all(texts: Sequence[str], folder: Path, voice: Voice, limit: int) -> Voiced:
    chars = unspoken_chars(texts, folder, voice) if isinstance(voice, ElevenLabs) else 0
    if chars > limit:
        raise VoiceNotConfigured(f"озвучка займёт {chars} знаков, потолок {limit}: поднимите ELEVENLABS_MAX_CHARS или сократите сценарий")
    if chars:
        log.info("ElevenLabs: %s знаков", chars)
    return Voiced(tuple(say(t, folder, voice) for t in texts), voice, chars)


def say_all(texts: Sequence[str], folder: Path, voice: Voice, fallback: Voice | None, limit: int) -> Voiced:
    """Весь ролик одним голосом: если основной отказал, запасной озвучивает все фразы с начала."""
    try:
        return _all(texts, folder, voice, limit)
    except SpeechFailed as error:
        if fallback is None:
            raise
        log.warning("%s; весь ролик озвучит запасной голос %s", error, fallback.describe()["voice"])
        return _all(texts, folder, fallback, limit)
