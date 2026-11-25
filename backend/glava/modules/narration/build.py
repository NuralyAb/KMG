"""Озвученные разборы главы: сценарий -> дорожка на шаг -> время каждой фразы."""

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from glava.modules.narration.script import Beat, Reader, write_script
from glava.modules.narration.voice import Speak, Voice, edge, seconds, speak_all


def _track(beats: Sequence[Beat], sounds: Sequence[bytes]) -> tuple[bytes, list[dict[str, Any]]]:
    placed: list[dict[str, Any]] = []
    at = 0.0
    for beat, sound in zip(beats, sounds, strict=True):
        end = at + seconds(sound)
        placed = [*placed, {"kind": beat.kind, "text": beat.text, "say": beat.say, "claim_id": beat.claim_id, "page": beat.page, "start": round(at, 2), "end": round(end, 2)}]
        at = end
    return b"".join(sounds), placed


def narrate(nodes: Sequence[Mapping], read: Reader, out: Path, cache: Path, voice: Voice, speak: Speak = edge) -> dict[str, Any]:
    """Дорожки кладутся в out; файл назван по содержимому, поэтому старая дорожка не останется под новым текстом."""
    scripts = {n["id"]: write_script(n, read) for n in nodes}
    phrases = list(dict.fromkeys(b.say for beats, _ in scripts.values() for b in beats))
    ready = dict(zip(phrases, speak_all(phrases, voice, cache, speak), strict=True))
    out.mkdir(parents=True, exist_ok=True)
    steps: dict[str, Any] = {}
    for step, (beats, _) in scripts.items():
        if not beats:
            continue
        audio, placed = _track(beats, [ready[b.say] for b in beats])
        name = f"{step.replace('.', '_')}.{hashlib.sha256(audio).hexdigest()[:8]}.mp3"
        (out / name).write_bytes(audio)
        steps = {**steps, step: {"audio": f"narration/{name}", "duration": placed[-1]["end"], "beats": placed}}
    kept = {Path(s["audio"]).name for s in steps.values()}
    for old in out.glob("*.mp3"):
        if old.name not in kept:
            old.unlink()
    return {"voice": {"provider": "microsoft", "voice": voice.name, "rate": voice.rate, "data_out": "текст фраз → Microsoft"}, "steps": steps,
            "skipped": {step: skipped for step, (_, skipped) in scripts.items() if skipped}, "silent": [s for s, (beats, _) in scripts.items() if not beats]}


def ready_narrations(narration: Mapping[str, Any], course: Path) -> dict[str, dict[str, Any]]:
    """Разборы для страницы курса: без дорожки на диске разбора нет, произношение странице не нужно."""
    return {step: {**found, "beats": [{k: v for k, v in b.items() if k != "say"} for b in found["beats"]]}
            for step, found in narration.get("steps", {}).items() if (course / found["audio"]).exists()}
