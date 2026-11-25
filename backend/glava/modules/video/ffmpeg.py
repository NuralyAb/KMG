"""FFmpeg: где лежит программа и замеры громкости."""

import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

TRUE_PEAK = -1.5


class FfmpegMissing(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg() -> str:
    """FFMPEG_EXE, затем PATH, затем программа из пакета imageio-ffmpeg."""
    own = os.environ.get("FFMPEG_EXE") or shutil.which("ffmpeg")
    if own:
        return own
    try:
        import imageio_ffmpeg
    except ImportError:
        raise FfmpegMissing("ffmpeg не найден: поставьте его, задайте FFMPEG_EXE или установите пакет imageio-ffmpeg") from None
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ebur(audio: Path) -> str:
    done = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(audio), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True)
    return done.stderr


def measured(audio: Path) -> tuple[float, float]:
    """Интегральная громкость, LUFS, и истинный пик, dBFS."""
    report = _ebur(audio)
    level = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", report)
    peak = re.findall(r"Peak:\s+(-?\d+(?:\.\d+)?) dBFS", report)
    if not level or not peak:
        raise RuntimeError("громкость не измерена")
    return float(level[-1]), float(peak[-1])


def samples_16k(audio: Path) -> bytes:
    """Моно, 16 кГц, 16 бит — вход распознавания."""
    done = subprocess.run([ffmpeg(), "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True)
    return done.stdout


def loudness_filter(audio: Path, target: float) -> str:
    """Второй проход нормализации: усиление на замеренную разницу и ограничитель пиков. Одним проходом loudnorm на коротких фразах промахивается."""
    level, _ = measured(audio)
    return f"volume={target - level:.2f}dB,alimiter=limit={10 ** (TRUE_PEAK / 20):.4f}:level=false"
