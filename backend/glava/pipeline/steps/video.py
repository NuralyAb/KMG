"""video и rebuild: ролик по одному узлу и пересборка шага с роликом после правки факта. Нужна группа пакетов video."""

import hashlib
import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from glava.modules.drawing.api import load_module, load_style
from glava.modules.errata.api import number_sources
from glava.modules.layer.api import pages_of
from glava.modules.llm.api import Provider, Reply
from glava.pipeline.chapter import Chapter, errata_of, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.steps.audit import build_audit
from glava.pipeline.steps.course import build_site
from glava.shared.evidence import verify_layer
from glava.shared.json_files import read, save
from glava.shared.paths import REPOSITORY, workspace

log = logging.getLogger("glava")
OpenProvider = Callable[[], Provider]


def list_voices() -> None:
    # pycairo ставится отдельно: группа video нужна только этим командам
    from glava.modules.video.api import VoiceNotConfigured
    from glava.modules.video.api import list_voices as available
    from glava.modules.video.api import voice_env

    try:
        rows = available(voice_env(REPOSITORY / ".env"))
    except VoiceNotConfigured as error:
        raise SystemExit(str(error)) from error
    for row in rows:
        log.info("%s", row)


def specs_folder(chapter: Chapter) -> Path:
    """Спецификации хранятся в git рядом со слоем: из них ролик пересобирается без модели."""
    return chapter.work / "video_specs"


def videos_folder(chapter: Chapter) -> Path:
    return workspace() / "out" / chapter.chapter_id / "videos"


def claim_marks(node: Mapping[str, Any]) -> dict[str, str]:
    """Отпечаток утверждений: по нему видно, что факт под фразой изменили."""
    return {c["id"]: hashlib.sha256(f"{c['text']}|{c['quote']}|{c['page_pdf']}".encode()).hexdigest()[:12] for c in node["claims"]}


def stale_beats(spec: Mapping[str, Any], node: Mapping[str, Any]) -> list[str]:
    now, then = claim_marks(node), spec.get("claim_marks") or {}
    return [f"фраза {i}: утверждение {b['claim_id']} изменилось" for i, b in enumerate(spec["beats"], start=1)
            if b["claim_id"] and then.get(b["claim_id"]) != now.get(b["claim_id"])]


def _node(chapter: Chapter, node_id: str) -> dict[str, Any]:
    node = next((n for n in read(chapter.work / "layer.json")["nodes"] if n["id"] == node_id), None)
    if node is None:
        raise SystemExit(f"узла {node_id} нет в слое")
    return node


def _narration(voice: str | None) -> Any:
    from glava.modules.video.api import (
        Narration,
        VoiceNotConfigured,
        max_chars,
        voice_env,
        voice_from_env,
    )

    env = voice_env(REPOSITORY / ".env")
    try:
        main = voice_from_env(env, voice)
        spare = env.get("VOICE_FALLBACK")
        return Narration(main, voice_from_env(env, spare) if spare else None, max_chars(env))
    except VoiceNotConfigured as error:
        raise SystemExit(str(error)) from error


def _pronunciation(domain: Path) -> str:
    files = (domain / "pronunciation.md", domain / "stress_dictionary.md")
    return "\n".join(f.read_text(encoding="utf-8") for f in files if f.exists())


def _template(chapter: Chapter, name: str) -> Any:
    file = chapter.domain / "video" / f"{name}.py"
    if not file.exists():
        raise SystemExit(f"шаблона {name} нет в {file.parent}")
    return load_module(file)


def _write_spec(chapter: Chapter, provider: Provider, node: Mapping[str, Any], kind: str, template_name: str) -> tuple[dict[str, Any], list[Reply]]:
    from glava.modules.video.api import make_spec

    video_id = f"{node['id'].replace('.', '_')}_{kind}"
    spec, replies = make_spec(provider, prompt_file("video"), node, _template(chapter, template_name), template_name, read(chapter.domain / "physics_checklist.json"), kind,
                              video_id, chapter.chapter_id)
    spec = {**spec, "claim_marks": claim_marks(node), "written_by": f"{provider.name}/{provider.model}"}
    save(specs_folder(chapter) / f"{video_id}.json", spec)
    return spec, replies


def _film(chapter: Chapter, spec: Mapping[str, Any], node: Mapping[str, Any], voice: str | None) -> dict[str, Any]:
    from glava.modules.video.api import VoiceNotConfigured, produce

    try:
        return produce(spec, node, _template(chapter, spec["template"]), load_style(chapter.domain), _pronunciation(chapter.domain),
                       read(chapter.domain / "physics_checklist.json"), chapter.work / "videos", videos_folder(chapter), _narration(voice))
    except VoiceNotConfigured as error:
        raise SystemExit(str(error)) from error


def build_video(chapter: Chapter, open_provider: OpenProvider, node_id: str, kind: str, template_name: str, voice: str | None = None, spec_only: bool = False) -> None:
    """Ролик по узлу: спецификацию пишет модель. spec_only — остановиться до озвучки, чтобы ментор посмотрел спецификацию до рендера."""
    node = _node(chapter, node_id)
    if not spec_only:
        _narration(voice)
    spec, replies = _write_spec(chapter, open_provider(), node, kind, template_name)
    passport = None if spec_only else _film(chapter, spec, node, voice)
    write_metrics(chapter, "video", 1, replies, passport["audio_check"]["duration_s"] if passport else 0)
    log.info("спецификация: %s", specs_folder(chapter) / f"{spec['video_id']}.json")


def checked_spec(chapter: Chapter, file: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    from glava.modules.video.api import spec_issues

    spec = json.loads(file.read_text(encoding="utf-8"))
    node = _node(chapter, spec["node_id"])
    issues = spec_issues(spec, node, _template(chapter, spec["template"]), read(chapter.domain / "physics_checklist.json"), spec["format"])
    if issues:
        raise SystemExit(f"{file.name}: спецификация не прошла проверку: " + "; ".join(issues[:8]))
    return spec, node


def film_spec(chapter: Chapter, file: Path, voice: str | None = None) -> None:
    """Ролик из готовой спецификации: модель не нужна."""
    spec, node = checked_spec(chapter, file)
    stale = stale_beats(spec, node)
    if stale:
        raise SystemExit(f"{file.name}: {'; '.join(stale[:5])}; запустите rebuild --node {node['id']}")
    passport = _film(chapter, spec, node, voice)
    write_metrics(chapter, "video", 1, [], passport["audio_check"]["duration_s"])


def accept_spec(chapter: Chapter, file: Path) -> None:
    """Человек прочитал спецификацию и подтверждает: фразы верны утверждениям в их нынешнем виде."""
    spec, node = checked_spec(chapter, file)
    save(file, {**spec, "claim_marks": claim_marks(node)})


def rebuild(chapter: Chapter, open_provider: OpenProvider, node_id: str | None, voice: str | None = None) -> None:
    """После правки факта в слое: проверка слоя, ролики узла и страница шага — одной командой. Модель нужна, только если правка задела фразу ролика."""
    layer = read(chapter.work / "layer.json")
    issues = [i for i in verify_layer(layer, pages_of(chapter.units), number_sources(errata_of(chapter))) if node_id is None or i.where.startswith(node_id)]
    if issues:
        raise SystemExit("слой не прошёл проверку: " + "; ".join(f"{i.where}: {i.message}" for i in issues[:8]))
    files = sorted(specs_folder(chapter).glob("*.json"))
    for file in files:
        spec = json.loads(file.read_text(encoding="utf-8"))
        if node_id is not None and spec["node_id"] != node_id:
            continue
        node = _node(chapter, spec["node_id"])
        stale, replies = stale_beats(spec, node), []
        if stale:
            log.info("%s: %s; спецификацию пишет модель заново", file.name, "; ".join(stale[:3]))
            spec, replies = _write_spec(chapter, open_provider(), node, spec["format"], spec["template"])
        else:
            spec, node = checked_spec(chapter, file)
        passport = _film(chapter, spec, node, voice)
        write_metrics(chapter, "video", 1, replies, passport["audio_check"]["duration_s"])
    build_audit(chapter.chapter_id)
    build_site(chapter)
