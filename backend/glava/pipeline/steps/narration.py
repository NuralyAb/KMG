"""narrate: озвученный разбор каждого шага бесплатным голосом. Модель не нужна, фразы берутся из слоя."""

import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from glava.modules.narration.api import Voice, VoiceFailed, narrate, reader
from glava.pipeline.chapter import Chapter
from glava.pipeline.steps.course import build_site
from glava.shared.json_files import read, read_or, save
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def _tables(domain: Path) -> str:
    files = (domain / "pronunciation.md", domain / "stress_dictionary.md")
    return "\n".join(f.read_text(encoding="utf-8") for f in files if f.exists())


def build_narration(chapter: Chapter, only: Sequence[str] | None = None, site: bool = True) -> None:
    """Разборы всех шагов; only — только этих (после правки факта), остальные остаются как были."""
    voice = Voice(os.environ.get("VOICE_EDGE_NAME", Voice.name), os.environ.get("VOICE_EDGE_RATE", Voice.rate))
    nodes = read(chapter.work / "layer.json")["nodes"]
    picked = nodes if only is None else [n for n in nodes if n["id"] in set(only)]
    try:
        made = narrate(picked, reader(_tables(chapter.domain)), workspace() / "out" / chapter.chapter_id / "narration", chapter.work / "narration_voice", voice,
                       prune=only is None)
    except VoiceFailed as error:
        raise SystemExit(str(error)) from error
    if only is not None:
        made = merged(read_or(chapter.work / "narration.json", {}), made, {n["id"] for n in picked})
    save(chapter.work / "narration.json", made)
    log.info("разборов: %s, минут: %.1f, пропущено фраз: %s, шагов без разбора: %s", len(made["steps"]), sum(s["duration"] for s in made["steps"].values()) / 60,
             sum(len(x) for x in made["skipped"].values()), made["silent"] or "нет")
    if site:
        build_site(chapter)


def merged(before: Mapping[str, Any], fresh: Mapping[str, Any], redone: set[str]) -> dict[str, Any]:
    """Разборы прежних шагов и заново озвученных."""
    def keep(part: str) -> dict[str, Any]:
        return {k: v for k, v in (before.get(part) or {}).items() if k not in redone}

    return {**before, "voice": fresh["voice"], "steps": {**keep("steps"), **fresh["steps"]}, "skipped": {**keep("skipped"), **fresh["skipped"]},
            "silent": [s for s in before.get("silent") or [] if s not in redone] + list(fresh["silent"])}
