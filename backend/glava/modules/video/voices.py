"""Голоса: ElevenLabs и онлайн-голос Microsoft. Наружу уходит только текст закадровых фраз."""

import asyncio
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

API = "https://api.elevenlabs.io/v1"
OWN_VARIABLES = ("VOICE_", "ELEVENLABS_")
EDGE_VOICE, EDGE_RATE = "ru-RU-DmitryNeural", "-6%"
EDGE_RETRIES = 14
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_RETRIES = 6
MAX_WAIT_S = 30
MAX_CHARS = 6000
STRESS_MARK = "́"
# v3 и v4 не принимают темп и стиль; language_code не принимает multilingual_v2
NO_SPEED = ("eleven_v4", "eleven_v3")
# 401 — ключ, 402 — тариф, 403 — права, 404 — голос, 422 — параметры: повтор не поможет
FATAL = frozenset({400, 401, 402, 403, 404, 422})


class SpeechFailed(RuntimeError):
    """Голос не ответил. Смешивать голоса в ролике нельзя: он озвучивается заново запасным голосом целиком."""


class VoiceNotConfigured(RuntimeError):
    """Не хватает ключа или голоса: это сообщение человеку, а не сбой."""


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


class Voice(Protocol):
    @property
    def key(self) -> str:
        """Всё, от чего зависит звук: входит в имя файла кэша."""
        ...

    def describe(self) -> dict[str, Any]: ...

    def prepare(self, text: str) -> str: ...

    def speak(self, text: str) -> tuple[bytes, list[Word]]: ...


def words_from_characters(characters: Sequence[str], starts: Sequence[float], ends: Sequence[float]) -> list[Word]:
    """ElevenLabs отдаёт время каждого знака; слово — непробельные знаки подряд, среди которых есть буква или цифра."""
    words: list[Word] = []
    text, begin, finish = "", 0.0, 0.0
    for char, start, end in [*zip(characters, starts, ends, strict=True), (" ", 0.0, 0.0)]:
        if not char.isspace():
            begin = begin if text else start
            text, finish = text + char, end
            continue
        if re.search(r"\w", text):
            words = [*words, Word(begin, finish, text)]
        text = ""
    return words


Post = Callable[[str, Mapping[str, str], Mapping[str, Any]], dict[str, Any]]


def _post(url: str, headers: Mapping[str, str], payload: Mapping[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, json.dumps(payload).encode(), {**headers, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as reply:  # noqa: S310 — адрес задан константой
        return json.loads(reply.read())


def _get(url: str, headers: Mapping[str, str]) -> dict[str, Any]:
    with urllib.request.urlopen(urllib.request.Request(url, headers=dict(headers)), timeout=60) as reply:  # noqa: S310
        return json.loads(reply.read())


def _reason(error: urllib.error.HTTPError) -> str:
    try:
        detail = json.loads(error.read()).get("detail", "")
    except (ValueError, AttributeError, OSError):
        return f"HTTP {error.code}"
    text = detail.get("message") or detail.get("status") if isinstance(detail, Mapping) else detail
    return f"HTTP {error.code}: {str(text)[:200]}"


@dataclass(frozen=True)
class ElevenLabs:
    api_key: str = field(repr=False)
    voice_id: str
    model: str = ELEVEN_MODEL
    speed: float = 0.95
    stability: float = 0.6
    similarity: float = 0.8
    style: float = 0.0
    seed: int = 7
    stress: bool = True
    post: Post = field(default=_post, repr=False, compare=False)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False, compare=False)

    @property
    def key(self) -> str:
        return f"elevenlabs|{self.voice_id}|{self.model}|{self.speed}|{self.stability}|{self.similarity}|{self.style}|{self.seed}"

    @property
    def _has_speed(self) -> bool:
        return not self.model.startswith(NO_SPEED)

    def describe(self) -> dict[str, Any]:
        return {"provider": "elevenlabs", "voice": self.voice_id, "model": self.model,
                "rate": f"speed {self.speed}" if self._has_speed else "темп голоса", "data_out": "текст закадровых фраз → api.elevenlabs.io"}

    def prepare(self, text: str) -> str:
        return text if self.stress else text.replace(STRESS_MARK, "")

    def payload(self, text: str) -> dict[str, Any]:
        settings: dict[str, Any] = {"stability": self.stability, "similarity_boost": self.similarity}
        if self._has_speed:
            settings = {**settings, "speed": self.speed, "style": self.style, "use_speaker_boost": True}
        body = {"text": text, "model_id": self.model, "seed": self.seed, "voice_settings": settings}
        return body if self.model == ELEVEN_MODEL else {**body, "language_code": "ru"}

    def speak(self, text: str) -> tuple[bytes, list[Word]]:
        url = f"{API}/text-to-speech/{self.voice_id}/with-timestamps?output_format=mp3_44100_128"
        detail = ""
        for attempt in range(ELEVEN_RETRIES):
            try:
                reply = self.post(url, {"xi-api-key": self.api_key}, self.payload(text))
                times = reply.get("alignment") or reply.get("normalized_alignment") or {}
                words = words_from_characters(times.get("characters", []), times.get("character_start_times_seconds", []),
                                              times.get("character_end_times_seconds", []))
                audio = base64.b64decode(reply.get("audio_base64") or "")
                if audio and words:
                    return audio, words
                detail = "пустой ответ"
            except urllib.error.HTTPError as error:
                detail = _reason(error)
                if error.code in FATAL:
                    break
            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                detail = repr(error)
            self.sleep(min(MAX_WAIT_S, 2**attempt))
        raise SpeechFailed(f"ElevenLabs не озвучил фразу: {detail}")


@dataclass(frozen=True)
class Edge:
    voice: str = EDGE_VOICE
    rate: str = EDGE_RATE

    @property
    def key(self) -> str:
        return f"{self.voice}|{self.rate}"

    def describe(self) -> dict[str, Any]:
        return {"provider": "microsoft", "voice": self.voice, "model": "edge-tts", "rate": self.rate, "data_out": "текст закадровых фраз → Microsoft"}

    def prepare(self, text: str) -> str:
        return text

    def speak(self, text: str) -> tuple[bytes, list[Word]]:
        detail = ""
        for attempt in range(EDGE_RETRIES):
            try:
                audio, words = asyncio.run(self._stream(text))
                if audio and words:
                    return audio, words
                detail = "пустой ответ"
            except Exception as error:  # noqa: BLE001 — сетевые ошибки edge_tts разнородны, причина уходит в сообщение
                detail = repr(error)
            time.sleep(min(MAX_WAIT_S, 2**attempt))
        raise SpeechFailed(f"голос {self.voice} не ответил {EDGE_RETRIES} раз: {detail[:200]}")

    async def _stream(self, text: str) -> tuple[bytes, list[Word]]:
        import edge_tts

        audio, words = b"", []
        async for chunk in edge_tts.Communicate(text, self.voice, rate=self.rate, boundary="WordBoundary").stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words = [*words, Word(start, start + chunk["duration"] / 1e7, chunk["text"])]
        return audio, words


def voice_env(file: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Настройки голоса: среда главнее файла .env. Из .env берутся только VOICE_* и ELEVENLABS_*, остальное код оттуда не читает."""
    found: dict[str, str] = {}
    if file.exists():
        for line in file.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip().startswith(OWN_VARIABLES):
                found[name.strip()] = value.strip().strip("\"'")
    current = os.environ if environ is None else environ
    return {k: v for k, v in {**found, **{k: v for k, v in current.items() if k.startswith(OWN_VARIABLES)}}.items() if v}


def _number(env: Mapping[str, str], name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(env.get(name, default))
    except ValueError:
        value = low - 1
    if not low <= value <= high:
        raise VoiceNotConfigured(f"{name}: нужно число от {low:g} до {high:g}")
    return value


def eleven_from_env(env: Mapping[str, str]) -> ElevenLabs:
    key, voice = env.get("ELEVENLABS_API_KEY", ""), env.get("ELEVENLABS_VOICE_ID", "")
    if not key:
        raise VoiceNotConfigured("нет ELEVENLABS_API_KEY: впишите ключ в .env")
    if not re.fullmatch(r"[A-Za-z0-9]{8,64}", voice):
        raise VoiceNotConfigured("нет ELEVENLABS_VOICE_ID: список голосов покажет команда voices")
    return ElevenLabs(key, voice, env.get("ELEVENLABS_MODEL", ELEVEN_MODEL), _number(env, "ELEVENLABS_SPEED", 0.95, 0.7, 1.2),
                      _number(env, "ELEVENLABS_STABILITY", 0.6, 0, 1), _number(env, "ELEVENLABS_SIMILARITY", 0.8, 0, 1),
                      _number(env, "ELEVENLABS_STYLE", 0.0, 0, 1), int(_number(env, "ELEVENLABS_SEED", 7, 0, 4294967295)),
                      env.get("ELEVENLABS_STRESS", "1") != "0")


def voice_from_env(env: Mapping[str, str], name: str | None = None) -> Voice:
    """VOICE_PROVIDER: elevenlabs или edge. По умолчанию ElevenLabs, если дан ключ, иначе голос Microsoft."""
    chosen = name or env.get("VOICE_PROVIDER") or ("elevenlabs" if env.get("ELEVENLABS_API_KEY") else "edge")
    if chosen == "elevenlabs":
        return eleven_from_env(env)
    if chosen == "edge":
        return Edge(env.get("VOICE_EDGE_NAME", EDGE_VOICE), env.get("VOICE_EDGE_RATE", EDGE_RATE))
    raise VoiceNotConfigured(f"голос {chosen}: бывает elevenlabs или edge")


def max_chars(env: Mapping[str, str]) -> int:
    return int(_number(env, "ELEVENLABS_MAX_CHARS", MAX_CHARS, 1, 1_000_000))


def list_voices(env: Mapping[str, str], get: Callable[[str, Mapping[str, str]], dict[str, Any]] = _get) -> list[str]:
    """Голоса, доступные ключу, и остаток знаков. Озвучка не запускается, знаки не тратятся."""
    key = env.get("ELEVENLABS_API_KEY")
    if not key:
        raise VoiceNotConfigured("нет ELEVENLABS_API_KEY: впишите ключ в .env")
    headers = {"xi-api-key": key}
    try:
        voices = get(f"{API}/voices", headers)["voices"]
    except urllib.error.HTTPError as error:
        raise VoiceNotConfigured(f"ElevenLabs не принял ключ: {_reason(error)}") from error
    except urllib.error.URLError as error:
        raise VoiceNotConfigured(f"нет связи с ElevenLabs: {error.reason}") from error
    rows = [f"{v['voice_id']}  {v['name']}  ({', '.join(str(x) for x in (v.get('labels') or {}).values())})" for v in voices]
    try:
        plan = get(f"{API}/user/subscription", headers)
        left = plan["character_limit"] - plan["character_count"]
        return [*rows, f"знаков осталось: {left} из {plan['character_limit']}, тариф {plan.get('tier')}"]
    except (urllib.error.URLError, KeyError):
        return [*rows, "остаток знаков не виден: у ключа нет права user_read, для озвучки оно не нужно"]
