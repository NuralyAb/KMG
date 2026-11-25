"""video: ролик по одному узлу."""

from glava.modules.drawing.api import load_module, load_style
from glava.modules.llm.api import Provider
from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.shared.json_files import read
from glava.shared.paths import workspace


def build_video(chapter: Chapter, provider: Provider, node_id: str, kind: str, template_name: str) -> None:
    """Ролик по одному узлу. Нужны пакеты группы video (pycairo, edge-tts, faster-whisper) и ffmpeg."""
    # pycairo ставится отдельно: группа video нужна только этой команде
    from glava.modules.video.api import make_spec, produce

    node = next((n for n in read(chapter.work / "layer.json")["nodes"] if n["id"] == node_id), None)
    if node is None:
        raise SystemExit(f"узла {node_id} нет в слое")
    template = load_module(chapter.domain / "video" / f"{template_name}.py")
    checklist = read(chapter.domain / "physics_checklist.json")
    video_id = f"{node_id.replace('.', '_')}_{kind}"
    spec, replies = make_spec(provider, prompt_file("video", chapter.is_english), node, template, template_name, checklist, kind, video_id, chapter.chapter_id)
    passport = produce(spec, node, template, load_style(chapter.domain), (chapter.domain / "pronunciation.md").read_text(encoding="utf-8"), checklist,
                       chapter.work / "videos", workspace() / "out" / chapter.chapter_id / "videos")
    write_metrics(chapter, "video", 1, replies, passport["audio_check"]["duration_s"])
