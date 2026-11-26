"""Отчёты и пересборка: покрытие шаблонами, проверка сдачи, цена процесса, устаревшие фразы ролика."""

import json
from pathlib import Path

import pytest
from glava.pipeline.chapter import Chapter
from glava.pipeline.steps import reports
from glava.pipeline.steps.course import course_videos
from glava.pipeline.steps.reports import (
    VideoTemplate,
    chapter_checks,
    process_rows,
    quality_rows,
    transfer_drop,
    series_checks,
    template_coverage,
    video_templates,
)
from glava.pipeline.steps.video import claim_marks, stale_beats
from glava.shared import paths
from glava.shared.json_files import save

CLAIM = {"id": "dm.a#c1", "text": "Давление в пласте падает.", "quote": "давление падает", "page_pdf": 5, "kind": "observation"}
NODE = {"id": "dm.a", "title": "Пуск скважины", "order": 1, "terms_introduced": [], "terms_used": [], "layers": {"main": {"text": "Дебит постоянный."}}, "claims": [CLAIM]}
SCORES = {"time": 2, "invisible": 2, "scale": 0, "counterintuitive": 1, "cause_effect": 1}
PASSPORT = {"node_id": "dm.a", "format": "9:16", "node_card": {"title": "Пуск скважины"}, "frames": [{"label": "симуляция"}, {"label": "симуляция"}], "physics_checklist": [],
            "audio_check": {"voice": "v", "rate": "r", "duration_s": 60, "paid_chars": 1000}}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    return tmp_path


def film(root, chapter, name="one", **over):
    folder = root / "out" / chapter / "videos"
    save(folder / f"{name}.passport.json", {**PASSPORT, **over})
    for suffix in (".mp4", ".srt"):
        (folder / f"{name}{suffix}").write_bytes(b"x")


def route(**over):
    return {"node_id": "dm.a", "format": "шортс", "video_scores": SCORES, "template": None, "hook_short": False, **over}


def test_template_is_taken_from_the_route_then_guessed_by_the_text():
    wave = VideoTemplate("pressure_wave", "модель", ("давлени", "дебит"))
    layer = {"nodes": [NODE]}
    assert template_coverage(layer, [route(template="pressure_wave")], [wave])[0]["status"] == "назначен маршрутизацией"
    guessed = template_coverage(layer, [route()], [wave])[0]
    assert guessed["template"] == "pressure_wave" and "подтвердить" in guessed["status"]
    assert template_coverage(layer, [route()], [VideoTemplate("риф", "модель", ("риф", "дебит"))])[0]["status"] == "нужен новый"
    assert template_coverage(layer, [route(format="карточки", video_scores={k: 0 for k in SCORES})], [wave]) == []


def test_videos_stage_picks_nodes_and_survives_failures(root, monkeypatch):
    from glava.pipeline.steps import videos

    chapter = Chapter("demo", "dm", "Глава", "Книга", root, (), "demo.md")
    other = {**NODE, "id": "dm.b", "order": 2}
    save(chapter.work / "layer.json", {"nodes": [NODE, other]})
    save(chapter.work / "routing.json", {"routes": [route(), route(node_id="dm.b", format="длинное видео", template="t"), route(node_id="dm.c")]})
    monkeypatch.setattr(videos, "video_templates", lambda d: [VideoTemplate("t", "модель", ())])
    monkeypatch.setattr(videos.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(videos, "build_video", lambda *a: (_ for _ in ()).throw(ValueError("спецификация не прошла")))
    rows = {r["node_id"]: r for r in videos.build_videos(chapter, lambda: None, 2)}
    assert rows["dm.a"]["result"] == "нужен новый шаблон"
    assert rows["dm.b"]["format"] == "wide" and rows["dm.b"]["result"].startswith("не снят")
    assert "dm.c" not in rows and (chapter.work / "video_report.json").exists()


def test_videos_limit_comes_from_the_environment():
    from glava.pipeline.steps.videos import limit_from_env

    assert (limit_from_env({}), limit_from_env({"GLAVA_VIDEOS": "0"})) == (2, 0)
    with pytest.raises(SystemExit):
        limit_from_env({"GLAVA_VIDEOS": "много"})


def test_video_templates_of_both_packs_describe_their_state_model():
    for domain in ("geology", "drilling"):
        found = video_templates(Path(__file__).resolve().parents[3] / "workspace" / "domain" / domain)
        assert found and all(t.model and t.fits for t in found)


def test_course_shows_only_finished_films(root):
    film(root, "demo")
    assert course_videos("demo") == {"dm.a": [{"title": "Пуск скважины", "src": "videos/one.mp4", "subtitles": "videos/one.srt", "format": "9:16", "label": "симуляция"}]}
    (root / "out" / "demo" / "videos" / "one.mp4").unlink()
    assert course_videos("demo") == {}


def test_missing_layer_is_the_only_remark(root):
    assert [c.name for c in chapter_checks("demo")] == ["учебный слой"]


def test_video_node_without_film_or_simulation_is_named(root):
    work = root / "work" / "demo"
    save(work / "layer.json", {"nodes": [NODE], "parts": [{"title": "Ч", "nodes": ["dm.a"]}]})
    save(work / "routing.json", {"routes": [route()]})
    closed = "видеоузлы закрыты роликом или интерактивом"
    assert not next(c for c in chapter_checks("demo") if c.name == closed).ok
    film(root, "demo")
    assert next(c for c in chapter_checks("demo") if c.name == closed).ok


def test_series_needs_two_chapters_and_one_voice():
    short, wide = {**PASSPORT}, {**PASSPORT, "format": "16:9"}
    assert all(c.ok for c in series_checks({"a": [short], "b": [wide]}))
    assert not series_checks({"a": [short, wide]})[0].ok
    other = {**wide, "audio_check": {**PASSPORT["audio_check"], "voice": "другой"}}
    assert not series_checks({"a": [short], "b": [other]})[1].ok


def test_process_counts_money_and_minutes(root, monkeypatch):
    save(root / "work" / "demo" / "layer.json", {"nodes": [NODE, NODE]})
    film(root, "demo")
    (root / "metrics.csv").write_text("chapter,stage,nodes,llm_tokens_in,llm_tokens_out,money_usd,person_minutes,mentor_minutes,video_seconds,manual_share\n"
                                      "demo,layer,2,1,1,4.0,0,3,0,0\ndemo,video,1,1,1,0.5,0,0,60,0\n", encoding="utf-8")
    monkeypatch.setattr(reports, "_edits", lambda: [{"chapter": "demo", "file": "workspace/work/demo/layer.json", "person_minutes": "6"},
                                                    {"chapter": "demo", "file": "workspace/work/demo/video_specs/x.json", "person_minutes": "10"}])
    row = process_rows(["demo"], usd_per_1k_chars=0.3)[0]
    assert (row["usd_per_node"], row["usd_per_video_minute"], row["mentor_minutes"]) == (2.0, 0.8, 3)
    assert (row["person_minutes_per_node"], row["person_minutes_per_video_minute"], row["elevenlabs_chars"]) == (3.0, 10.0, 1000)


def test_changed_fact_marks_its_phrase():
    spec = {"claim_marks": claim_marks(NODE), "beats": [{"claim_id": None}, {"claim_id": "dm.a#c1"}]}
    assert stale_beats(spec, NODE) == []
    changed = {**NODE, "claims": [{**CLAIM, "text": "Давление в пласте растёт."}]}
    assert stale_beats(spec, changed) == ["фраза 2: утверждение dm.a#c1 изменилось"]


def test_rebuild_films_from_the_spec_and_rebuilds_the_course(root, monkeypatch):
    from glava.pipeline.steps import video

    chapter = Chapter("demo", "dm", "Глава", "Книга", root, (), "demo.md")
    save(chapter.work / "layer.json", {"nodes": [NODE]})
    save(chapter.work / "video_specs" / "one.json", {"video_id": "one", "node_id": "dm.a", "format": "short", "template": "t", "claim_marks": claim_marks(NODE), "beats": []})
    calls = []
    monkeypatch.setattr(video, "verify_layer", lambda *a: [])
    monkeypatch.setattr(video, "checked_spec", lambda c, f: (json.loads(f.read_text(encoding="utf-8")), NODE))
    monkeypatch.setattr(video, "_film", lambda c, s, n, v: calls.append(s["video_id"]) or {"audio_check": {"duration_s": 1}})
    monkeypatch.setattr(video, "write_metrics", lambda *a: None)
    monkeypatch.setattr(video, "build_audit", lambda c: calls.append("audit"))
    monkeypatch.setattr(video, "build_site", lambda c: calls.append("course"))
    video.rebuild(chapter, lambda: pytest.fail("модель не нужна"), "dm.a")
    assert calls == ["one", "audit", "course"]


def test_rebuild_asks_the_model_only_when_the_fact_changed(root, monkeypatch):
    from glava.pipeline.steps import video

    chapter = Chapter("demo", "dm", "Глава", "Книга", root, (), "demo.md")
    save(chapter.work / "layer.json", {"nodes": [NODE]})
    save(chapter.work / "video_specs" / "one.json", {"video_id": "one", "node_id": "dm.a", "format": "short", "template": "t", "claim_marks": {}, "beats": [{"claim_id": "dm.a#c1"}]})
    asked = []
    monkeypatch.setattr(video, "verify_layer", lambda *a: [])
    monkeypatch.setattr(video, "_write_spec", lambda c, p, n, k, t: asked.append(p) or ({"video_id": "one"}, []))
    monkeypatch.setattr(video, "_film", lambda *a: {"audio_check": {"duration_s": 1}})
    for name in ("write_metrics", "build_audit", "build_site"):
        monkeypatch.setattr(video, name, lambda *a: None)
    video.rebuild(chapter, lambda: "модель", None)
    assert asked == ["модель"]


def _quiet_rebuild(video, monkeypatch, calls):
    monkeypatch.setattr(video, "checked_spec", lambda c, f: (json.loads(f.read_text(encoding="utf-8")), NODE))
    monkeypatch.setattr(video, "_film", lambda c, s, n, v: calls.append(s["video_id"]) or {"audio_check": {"duration_s": 1}})
    monkeypatch.setattr(video, "build_narration", lambda c, only, site: calls.append(("narrate", tuple(only), site)))
    monkeypatch.setattr(video, "write_metrics", lambda *a: None)
    monkeypatch.setattr(video, "build_audit", lambda c: calls.append("audit"))
    monkeypatch.setattr(video, "build_site", lambda c: calls.append("course"))


def test_rebuild_narrates_touched_steps_and_skips_untouched_films(root, monkeypatch):
    from glava.pipeline.steps import video

    chapter = Chapter("demo", "dm", "Глава", "Книга", root, (), "demo.md")
    save(chapter.work / "layer.json", {"nodes": [NODE]})
    save(chapter.work / "narration.json", {"steps": {}})
    save(chapter.work / "video_specs" / "one.json", {"video_id": "one", "node_id": "dm.a", "format": "short", "template": "t", "claim_marks": claim_marks(NODE), "beats": []})
    film(root, "demo")
    calls = []
    monkeypatch.setattr(video, "verify_layer", lambda *a: [])
    _quiet_rebuild(video, monkeypatch, calls)
    video.rebuild(chapter, lambda: pytest.fail("модель не нужна"), None)
    assert calls == ["audit", "course"]
    calls.clear()
    video.rebuild(chapter, lambda: pytest.fail("модель не нужна"), None, steps=["dm.a"])
    assert calls == ["one", ("narrate", ("dm.a",), False), "audit", "course"]


def test_rebuild_lets_a_number_outside_the_quote_only_with_accept(root, monkeypatch):
    from glava.pipeline.steps import video
    from glava.shared.evidence import Issue

    chapter = Chapter("demo", "dm", "Глава", "Книга", root, (), "demo.md")
    save(chapter.work / "layer.json", {"nodes": [NODE]})
    monkeypatch.setattr(video, "verify_layer", lambda *a: [Issue("number_not_in_source", "dm.a:c1", "чисел нет")])
    calls = []
    _quiet_rebuild(video, monkeypatch, calls)
    with pytest.raises(SystemExit):
        video.rebuild(chapter, lambda: pytest.fail("модель не нужна"), None)
    video.rebuild(chapter, lambda: pytest.fail("модель не нужна"), None, accept=True)
    assert calls == ["audit", "course"]


def test_course_and_narration_load_without_the_book(root):
    from glava.modules.library.api import LibraryError
    from glava.pipeline.chapter import load_chapter

    save(root / "chapters.json", {"root": "нет_такой_папки", "pdf_root": "нет", "chapters": {"demo": {"file": "demo.md", "pages": [[1, 2]], "prefix": "dm", "domain": "geology",
                                                                                                    "title": "Т", "book": "К"}}})
    assert load_chapter("demo", need_text=False).units == ()
    with pytest.raises(LibraryError, match="GLAVA_BOOKS"):
        load_chapter("demo")


def test_transfer_compares_control_with_the_training_mean(root, monkeypatch):
    monkeypatch.setattr(reports, "_edits", lambda: [])
    def chapter(name, claims, flagged):
        work = root / "work" / name
        save(work / "layer.json", {"nodes": [{**NODE, "claims": [CLAIM] * claims}]})
        save(work / "coverage.json", {"rows": [{"node_ids": ["dm.a"]}, {"node_ids": [], "reason": "оглавление"}, {"node_ids": []}]})
        save(work / "audit.json", {"flagged": [{}] * flagged, "early_terms": []})
    chapter("latyshova_gl5_par17-20", 20, 2)
    chapter("vendelshtein_gl1", 10, 2)
    rows = quality_rows({"latyshova_gl5_par17-20": {"pages": [[1, 10]]}, "vendelshtein_gl1": {"pages": [[1, 10]]}, "kuznetsov_gl10": {"pages": [[1, 5]]}})
    assert [r["chapter"] for r in rows] == ["latyshova_gl5_par17-20", "vendelshtein_gl1"]  # глава без слоя не считается
    first = rows[0]
    assert (first["split"], first["claims_per_page"], first["covered_share"], first["skipped_with_reason"], first["units_lost"], first["flagged_share"]) == ("обучение", 2.0, 0.333, 1, 1, 0.1)
    assert first["verify_follows"] is None
    drop = transfer_drop(rows)
    assert drop == [{"chapter": "vendelshtein_gl1", "complete": True, "claims_per_page": -0.5, "covered_share": 0.0, "flagged_share": -1.0}]
    # обучающая глава, собранная не на все узлы плана, эталоном не служит
    save(root / "work" / "latyshova_gl5_par17-20" / "plan.json", {"nodes": [{}, {}]})
    rows = quality_rows({"latyshova_gl5_par17-20": {"pages": [[1, 10]]}, "vendelshtein_gl1": {"pages": [[1, 10]]}})
    assert rows[0]["complete"] is False and transfer_drop(rows) == [{"chapter": "vendelshtein_gl1", "complete": True}]
