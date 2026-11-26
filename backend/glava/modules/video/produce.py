"""Сборка ролика: спецификация -> голос -> проверки дорожки -> видео -> паспорт."""

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from glava.modules.video.check import (
    hook_problems,
    pace_problems,
    recognise,
    speech_rate,
    sync_error,
    word_error_rate,
)
from glava.modules.video.ffmpeg import measured
from glava.modules.video.passport import build_passport
from glava.modules.video.render import render_audio, render_video
from glava.modules.video.speech import dictionaries, say_all, spoken
from glava.modules.video.timeline import place
from glava.modules.video.voices import Voice

log = logging.getLogger("glava")
MAX_WER = 0.10
WPM = (110, 150)
LUFS_RANGE = (-17.0, -15.0)
MAX_PEAK = -0.5
MAX_SYNC_S = 0.5
SECONDS = {"short": (40, 90), "wide": (90, 180)}


@dataclass(frozen=True)
class Narration:
    voice: Voice
    fallback: Voice | None = None
    max_chars: int = 6000


def audio_problems(audio: Mapping[str, Any]) -> list[str]:
    problems = [f"слов с ошибкой {audio['wer']:.0%}, можно {MAX_WER:.0%}"] if audio["wer"] > MAX_WER else []
    problems += [f"темп {audio['words_per_minute']:.0f} слов в минуту"] if not WPM[0] <= audio["words_per_minute"] <= WPM[1] else []
    problems += [f"громкость {audio['lufs']} LUFS"] if not LUFS_RANGE[0] <= audio["lufs"] <= LUFS_RANGE[1] else []
    problems += [f"пик {audio['true_peak']} дБ: возможен клиппинг"] if audio.get("true_peak", -9) > MAX_PEAK else []
    sync = audio.get("sync_s", 0)
    problems += ["синхрон не измерен: распознано мало слов"] if sync is None else []
    return problems + ([f"рассинхрон {sync} с, можно {MAX_SYNC_S}"] if sync and sync > MAX_SYNC_S else [])


def length_problems(seconds: float, kind: str) -> list[str]:
    low, high = SECONDS[kind]
    return [] if low <= seconds <= high else [f"длина {seconds:.0f} с, нужно {low}–{high}"]


def produce(
    spec: Mapping[str, Any], node: Mapping[str, Any], template: ModuleType, style: Mapping[str, Any], pronunciation: str,
    checklist: Sequence[Mapping[str, str]], work: Path, out: Path, narration: Narration,
) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    computed = [template.plaque(spec["params"], spec["format"])] if hasattr(template, "plaque") else []
    spec = {**spec, "plaque": list(dict.fromkeys([*computed, *spec["plaque"]])), "exaggerations": list(dict.fromkeys([*computed, *spec["exaggerations"]])),
            "claim_kinds": {c["id"]: c["kind"] for c in node["claims"] if c.get("kind")}}
    short, stress = dictionaries(pronunciation)
    voiced = say_all([spoken(b["say"], short, stress) for b in spec["beats"]], work / "voice", narration.voice, narration.fallback, narration.max_chars)
    placed, total = place(spec["beats"], voiced.speeches)
    scene = out / f"{spec['video_id']}.scene.json"
    scene.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    track = render_audio(placed, total, work / f"{spec['video_id']}.wav")
    heard = recognise(track)
    lufs, peak = measured(track)
    expected = " ".join(spoken(b["say"], short, {}) for b in spec["beats"])
    audio = {
        **voiced.voice.describe(), "wer": round(word_error_rate(expected, heard.text), 3), "heard": heard.text, "words_per_minute": round(speech_rate(placed), 1),
        "lufs": lufs, "true_peak": peak, "duration_s": round(total, 1), "sync_s": sync_error(placed, heard.words), "paid_chars": voiced.paid_chars,
        "sync": "95 % слов дорожки звучат не дальше sync_s от времени, к которому привязана сцена; слова нашла локальная модель Whisper",
    }
    audio = {**audio, "problems": [*audio_problems(audio), *length_problems(total, spec["format"]), *hook_problems(placed), *pace_problems(placed, total)]}
    video = render_video(spec, placed, total, template, style, track, out / f"{spec['video_id']}.mp4")
    answers = {k: (v["answer"], v["note"]) for k, v in spec["physics"].items()}
    passport = build_passport(spec, node, placed, scene.name, checklist, answers, audio)
    (out / f"{spec['video_id']}.passport.json").write_text(json.dumps(passport, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    log.info("ролик %s, %.0f с, замечания к дорожке: %s", video, total, audio["problems"] or "нет")
    return passport
