"""Озвучка онлайн-голосом Microsoft: наружу уходит только текст сценария. Ответы кэшируются, отказы повторяются."""

import asyncio
import hashlib
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

VOICE = "ru-RU-DmitryNeural"
RATE = "-6%"
RETRIES = 6
TAIL = 0.15


class SpeechFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


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


async def _stream(text: str, voice: str, rate: str) -> tuple[bytes, list[Word]]:
    import edge_tts

    audio, words = b"", []
    async for chunk in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / 1e7
            words = [*words, Word(start, start + chunk["duration"] / 1e7, chunk["text"])]
    return audio, words


def say(text: str, folder: Path, voice: str = VOICE, rate: str = RATE) -> Speech:
    key = hashlib.sha256(f"{voice}|{rate}|{text}".encode()).hexdigest()[:24]
    audio_path, words_path = folder / f"{key}.mp3", folder / f"{key}.json"
    if not words_path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        audio, words = _with_retries(text, voice, rate)
        audio_path.write_bytes(audio)
        words_path.write_text(json.dumps([[w.start, w.end, w.text] for w in words], ensure_ascii=False), encoding="utf-8")
    words = tuple(Word(*w) for w in json.loads(words_path.read_text(encoding="utf-8")))
    return Speech(audio_path, words[-1].end + TAIL, words)


def _with_retries(text: str, voice: str, rate: str) -> tuple[bytes, list[Word]]:
    detail = ""
    for attempt in range(RETRIES):
        try:
            audio, words = asyncio.run(_stream(text, voice, rate))
            if audio and words:
                return audio, words
            detail = "пустой ответ"
        except Exception as error:  # noqa: BLE001 — сетевые ошибки edge_tts разнородны, причина уходит в сообщение
            detail = repr(error)
        time.sleep(min(20, 2**attempt))
    raise SpeechFailed(f"голос {voice} не ответил {RETRIES} раз: {detail[:200]}; смените голос всей серии или повторите позже")
