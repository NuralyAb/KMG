"""Сборка ролика: спецификация -> голос -> проверки дорожки -> видео -> паспорт."""

import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from glava.video.check import loudness, recognise, speech_rate, word_error_rate
from glava.video.passport import build_passport
from glava.video.render import render_audio, render_video
from glava.video.speech import RATE, VOICE, dictionaries, say, spoken
from glava.video.timeline import place

log = logging.getLogger("glava")
MAX_WER = 0.10
WPM = (110, 150)
LUFS_RANGE = (-17.0, -15.0)


def audio_problems(audio: Mapping[str, Any]) -> list[str]:
    problems = [f"слов с ошибкой {audio['wer']:.0%}, можно {MAX_WER:.0%}"] if audio["wer"] > MAX_WER else []
    problems += [f"темп {audio['words_per_minute']:.0f} слов в минуту"] if not WPM[0] <= audio["words_per_minute"] <= WPM[1] else []
    return problems + ([f"громкость {audio['lufs']} LUFS"] if not LUFS_RANGE[0] <= audio["lufs"] <= LUFS_RANGE[1] else [])


def produce(
    spec: Mapping[str, Any], node: Mapping[str, Any], template: ModuleType, style: Mapping[str, Any], pronunciation: str,
    checklist: Sequence[Mapping[str, str]], work: Path, out: Path,
) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    honest = [template.plaque(spec["params"], spec["format"]), *spec["plaque"]] if hasattr(template, "plaque") else list(spec["plaque"])
    spec = {**spec, "plaque": honest, "exaggerations": list(dict.fromkeys([*honest[:1], *spec["exaggerations"]]))}
    short, stress = dictionaries(pronunciation)
    speeches = [say(spoken(b["say"], short, stress), work / "voice") for b in spec["beats"]]
    placed, total = place(spec["beats"], speeches)
    scene = out / f"{spec['video_id']}.scene.json"
    scene.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    track = render_audio(placed, total, work / f"{spec['video_id']}.wav")
    expected = " ".join(spoken(b["say"], short, {}) for b in spec["beats"])
    heard = recognise(track)
    audio = {
        "voice": VOICE, "rate": RATE, "wer": round(word_error_rate(expected, heard), 3), "heard": heard, "words_per_minute": round(speech_rate(placed), 1),
        "lufs": loudness(track), "duration_s": round(total, 1), "sync": "каждое действие сцены начинается и заканчивается вместе со своей фразой по меткам слов",
    }
    audio = {**audio, "problems": audio_problems(audio)}
    video = render_video(spec, placed, total, template, style, track, out / f"{spec['video_id']}.mp4")
    answers = {k: (v["answer"], v["note"]) for k, v in spec["physics"].items()}
    passport = build_passport(spec, node, placed, scene.name, checklist, answers, audio)
    (out / f"{spec['video_id']}.passport.json").write_text(json.dumps(passport, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    log.info("ролик %s, %.0f с, замечания к дорожке: %s", video, total, audio["problems"] or "нет")
    return passport
