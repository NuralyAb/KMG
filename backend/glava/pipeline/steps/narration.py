"""narrate: озвученный разбор каждого шага бесплатным голосом. Модель не нужна, фразы берутся из слоя."""

import logging
import os
from pathlib import Path

from glava.modules.narration.api import Voice, VoiceFailed, narrate, reader
from glava.pipeline.chapter import Chapter
from glava.pipeline.steps.course import build_site
from glava.shared.json_files import read, save
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def _tables(domain: Path) -> str:
    files = (domain / "pronunciation.md", domain / "stress_dictionary.md")
    return "\n".join(f.read_text(encoding="utf-8") for f in files if f.exists())


def build_narration(chapter: Chapter) -> None:
    voice = Voice(os.environ.get("VOICE_EDGE_NAME", Voice.name), os.environ.get("VOICE_EDGE_RATE", Voice.rate))
    nodes = read(chapter.work / "layer.json")["nodes"]
    try:
        made = narrate(nodes, reader(_tables(chapter.domain)), workspace() / "out" / chapter.chapter_id / "narration", chapter.work / "narration_voice", voice)
    except VoiceFailed as error:
        raise SystemExit(str(error)) from error
    save(chapter.work / "narration.json", made)
    log.info("разборов: %s, минут: %.1f, пропущено фраз: %s, шагов без разбора: %s", len(made["steps"]), sum(s["duration"] for s in made["steps"].values()) / 60,
             sum(len(x) for x in made["skipped"].values()), made["silent"] or "нет")
    build_site(chapter)
