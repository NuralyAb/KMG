"""Время ролика: фразы встают по длине речи, состояние сцены меняется вместе с фразой."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from glava.video.speech import Speech

LEAD = 0.2
GAP = 0.45
FINAL_HOLD = 2.5
MOVE_SHARE = 0.9


@dataclass(frozen=True)
class Placed:
    beat: Mapping[str, Any]
    start: float
    end: float
    speech: Speech


def place(beats: Sequence[Mapping[str, Any]], speeches: Sequence[Speech]) -> tuple[list[Placed], float]:
    placed: list[Placed] = []
    clock = LEAD
    for beat, speech in zip(beats, speeches, strict=True):
        placed = [*placed, Placed(beat, clock, clock + speech.duration, speech)]
        clock += speech.duration + GAP + float(beat.get("pause_after") or 0)
    return placed, clock - GAP + FINAL_HOLD


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def state_at(t: float, placed: Sequence[Placed], initial: Mapping[str, float]) -> dict[str, float]:
    """Состояние — свёртка действий: каждое число плавно идёт к цели, пока звучит его фраза."""
    state = {k: float(v) for k, v in initial.items()}
    for item in placed:
        if t <= item.start:
            break
        share = _ease((t - item.start) / max(0.1, (item.end - item.start) * MOVE_SHARE))
        goals = {k: float(v) for k, v in item.beat["action"].items()}
        state = {**state, **{k: state.get(k, 0.0) + (goal - state.get(k, 0.0)) * share for k, goal in goals.items()}}
    return state


def current(t: float, placed: Sequence[Placed]) -> Placed:
    started = [p for p in placed if p.start <= t]
    return started[-1] if started else placed[0]


def _stamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(placed: Sequence[Placed]) -> str:
    return "\n".join(f"{i}\n{_stamp(p.start)} --> {_stamp(p.end + 0.2)}\n{p.beat['say']}\n" for i, p in enumerate(placed, start=1))
