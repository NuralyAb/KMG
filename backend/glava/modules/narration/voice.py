"""Бесплатный голос Microsoft для разборов: наружу уходит только текст фраз. Готовые фразы берутся из кэша."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

VOICE, RATE = "ru-RU-DmitryNeural", "-6%"
RETRIES = 30
MAX_WAIT_S = 5
PARALLEL = 4
# edge отдаёт mp3 с постоянным потоком 48 кбит/с: длина дорожки — это её размер
BYTES_PER_SECOND = 48_000 / 8


class VoiceFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class Voice:
    name: str = VOICE
    rate: str = RATE

    @property
    def key(self) -> str:
        return f"{self.name}|{self.rate}"


Speak = Callable[[str, Voice], Awaitable[bytes]]


async def edge(text: str, voice: Voice) -> bytes:
    import edge_tts

    audio = b""
    async for chunk in edge_tts.Communicate(text, voice.name, rate=voice.rate).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return audio


def _file(text: str, voice: Voice, cache: Path) -> Path:
    return cache / f"{hashlib.sha256(f'{voice.key}|{text}'.encode()).hexdigest()[:24]}.mp3"


async def _phrase(text: str, voice: Voice, cache: Path, speak: Speak, gate: asyncio.Semaphore) -> bytes:
    file = _file(text, voice, cache)
    if file.exists():
        return file.read_bytes()
    detail = "пустой ответ"
    async with gate:
        for attempt in range(RETRIES):
            try:
                audio = await speak(text, voice)
            except Exception as error:  # noqa: BLE001 — сетевые ошибки edge_tts разнородны, причина уходит в сообщение
                detail, audio = repr(error), b""
            if audio:
                cache.mkdir(parents=True, exist_ok=True)
                file.write_bytes(audio)
                return audio
            await asyncio.sleep(min(MAX_WAIT_S, 2**attempt))
    raise VoiceFailed(f"голос {voice.name} не ответил {RETRIES} раз: {detail[:200]}")


def speak_all(phrases: Sequence[str], voice: Voice, cache: Path, speak: Speak = edge) -> list[bytes]:
    async def run() -> list[bytes]:
        gate = asyncio.Semaphore(PARALLEL)
        return list(await asyncio.gather(*(_phrase(p, voice, cache, speak, gate) for p in phrases)))

    return asyncio.run(run())


def seconds(audio: bytes) -> float:
    return len(audio) / BYTES_PER_SECOND
