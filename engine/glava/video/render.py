"""Кадры из модели состояния -> видео; дорожка из фраз по таймлайну с громкостью −16 LUFS."""

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import cairo

from glava.video.draw import fill_rect
from glava.video.overlay import LAYOUTS, draw_overlay
from glava.video.timeline import Placed, srt, state_at

FPS = 30
LUFS = -16


def frame(t: float, spec: Mapping[str, Any], placed: Sequence[Placed], template: ModuleType, style: Mapping[str, Any]) -> cairo.ImageSurface:
    layout = LAYOUTS[spec["format"]]
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, layout.width, layout.height)
    ctx = cairo.Context(surface)
    fill_rect(ctx, 0, 0, layout.width, layout.height, style["background"])
    state = state_at(t, placed, template.initial(spec["params"]))
    template.draw(ctx, layout.scene, spec["params"], state, t, style, layout)
    draw_overlay(ctx, t, placed, spec, style, layout)
    return surface


def _run(command: Sequence[str], **kwargs: Any) -> None:
    done = subprocess.run(command, capture_output=True, check=False, **kwargs)
    if done.returncode:
        raise RuntimeError(f"ffmpeg: {done.stderr.decode('utf-8', 'replace')[-600:]}")


def render_audio(placed: Sequence[Placed], total: float, out: Path) -> Path:
    inputs = [x for p in placed for x in ("-i", str(p.speech.path))]
    delays = [f"[{i}:a]aresample=48000,adelay={round(p.start * 1000)}:all=1[a{i}]" for i, p in enumerate(placed)]
    mix = "".join(f"[a{i}]" for i in range(len(placed))) + f"amix=inputs={len(placed)}:normalize=0,apad=whole_dur={total:.3f}[mix]"
    raw = out.with_suffix(".raw.wav")
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join([*delays, mix]), "-map", "[mix]", "-ac", "1", "-t", f"{total:.3f}", str(raw)])
    _run(["ffmpeg", "-y", "-i", str(raw), "-af", f"loudnorm=I={LUFS}:TP=-1.5:LRA=11", "-ar", "48000", str(out)])
    raw.unlink()
    return out


def render_video(spec: Mapping[str, Any], placed: Sequence[Placed], total: float, template: ModuleType, style: Mapping[str, Any], audio: Path, out: Path) -> Path:
    layout = LAYOUTS[spec["format"]]
    subtitles = out.with_suffix(".srt")
    subtitles.write_text(srt(placed), encoding="utf-8")
    command = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0", "-s", f"{layout.width}x{layout.height}", "-r", str(FPS), "-i", "-",
               "-i", str(audio), "-i", str(subtitles), "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text", "-metadata:s:s:0", "language=rus", "-movflags", "+faststart", str(out)]
    with out.with_suffix(".log").open("wb") as log, subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log) as process:
        assert process.stdin is not None
        for i in range(round(total * FPS)):
            process.stdin.write(bytes(frame(i / FPS, spec, placed, template, style).get_data()))
        process.stdin.close()
        if process.wait():
            raise RuntimeError(f"ffmpeg не собрал видео, журнал: {out.with_suffix('.log')}")
    out.with_suffix(".log").unlink()
    return out
