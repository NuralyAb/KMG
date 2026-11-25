"""Симуляторы шага: готовые сцены, ход работы агента и что видно ученику."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import CHAPTER, EMPTY_CHAPTER, ORIGIN, data_of, error_of, wait_for
from fastapi import FastAPI
from fastapi.testclient import TestClient
from glava.modules.catalog.api import Repository
from glava.modules.runs.api import RunRecord
from glava.modules.simulations.progress import STAGES, read_progress
from glava.modules.simulations.service import Simulations

NODE = "alpha.first"
URL = f"/api/chapters/{CHAPTER}/nodes/{NODE}/simulations"
LOG = ["✓ facts: 11 утверждений из слоя, без модели", "> design: запрос ≈2758 токенов, sonnet", "✓ design", "> model: запрос ≈4537 токенов, sonnet", "✓ model"]


def put_scene(root: Path, **scenes: Any) -> None:
    out = root / "out" / CHAPTER
    (out / "assets" / "sim").mkdir(parents=True)
    (out / "assets" / "sim" / "player.html").write_text("", encoding="utf-8")
    (out / "simulations").mkdir()
    (out / "simulations" / "log_fresh.webp").write_bytes(b"x")
    (out / "simulations.js").write_text(f"globalThis.SIM_SCENES={json.dumps({'scenes': scenes})};\n", encoding="utf-8")


def record(state: str, **args: Any) -> RunRecord:
    return RunRecord("r1", "simulation", CHAPTER, {"node": NODE, **args}, state, created_at="2026-01-01", started_at="2026-01-01T00:00:00+00:00")


def service(app: FastAPI, lines: list[str], *records: RunRecord) -> Simulations:
    runs = SimpleNamespace(records=lambda: list(records), log_lines=lambda _: lines)
    return Simulations(app.state.container.get(Repository), runs)


def states(lines: list[str], is_running: bool = True) -> dict[str, str]:
    return read_progress(lines, is_running).stages


def test_next_stage_is_shown_while_the_agent_is_silent() -> None:
    assert states([])["facts"] == "now"
    assert [s for s in STAGES if states(LOG)[s] == "done"] == ["facts", "design", "model"]
    assert states(LOG)["scene"] == "now"


def test_scene_and_game_go_together() -> None:
    both = states([*LOG, "> scene: запрос", "> game: запрос", "✓ game"])

    assert (both["scene"], both["game"], both["look"]) == ("now", "done", "wait")


def test_retry_and_look_close_the_earlier_stages() -> None:
    again = read_progress([*LOG, "> scene: запрос", "  проверка: 1 замечаний", "> scene (исправление 2): запрос ≈5 токенов, sonnet"], True)
    looking = states([*LOG, "> look: 4 кадра, автозамечаний 0", "✓ вычитка: исправлено 2"])

    assert again.retry == 2
    assert (looking["scene"], looking["game"], looking["look"]) == ("done", "done", "now")


def test_course_is_the_last_stage() -> None:
    built = [*LOG, "> look: 4 кадра", "привязано к шагу alpha.first", "✓ Готово: sims/x.json"]

    assert states(built)["course"] == "now"
    assert set(states([*built, "курс: C:/out/index.html"], False).values()) == {"done"}


@pytest.mark.parametrize("sign", ["✗", "■"])
def test_reason_is_kept(sign: str) -> None:
    ended = read_progress([*LOG, "> scene: запрос", f"{sign} общий потолок 1.5", "Потрачено: 1.40"], False)

    assert ended.reason == "общий потолок 1.5"
    assert (ended.stages["model"], ended.stages["scene"], ended.stages["game"]) == ("done", "failed", "wait")


def test_node_shows_only_its_published_scenes(client: TestClient, root: Path) -> None:
    put_scene(root, log_fresh={"title": "Каротаж", "goal": "Найти пласт", "provenance": "симуляция", "node_id": NODE},
              other={"title": "Чужая", "node_id": "alpha.second"}, **{"../x": {"node_id": NODE}})

    found = data_of(client.get(URL))

    assert found["run"] is None
    assert found["scenes"] == [{"id": "log_fresh", "title": "Каротаж", "goal": "Найти пласт", "label": "симуляция",
                                "poster_url": f"/course/{CHAPTER}/simulations/log_fresh.webp", "player_url": f"/course/{CHAPTER}/assets/sim/player.html#log_fresh"}]


def test_no_course_no_scenes_and_unknown_node(client: TestClient, root: Path) -> None:
    assert data_of(client.get(URL))["scenes"] == []
    put_scene(root)
    (root / "out" / CHAPTER / "simulations.js").write_text("битый", encoding="utf-8")
    assert data_of(client.get(URL))["scenes"] == []
    error_of(client.get(f"/api/chapters/{CHAPTER}/nodes/alpha.nope/simulations"), 404)


def test_last_run_of_the_node_is_shown(client: TestClient) -> None:
    started = client.post("/api/runs", json={"command": "simulation", "chapter": CHAPTER, "node": NODE, "until": "design"}, headers=ORIGIN)
    data_of(started, 201)

    run = wait_for(lambda: (r := data_of(client.get(URL))["run"])["state"] == "done" and r)

    assert run["is_design_only"] is True
    assert [s["name"] for s in run["stages"]] == ["facts", "design"]
    assert data_of(client.get(f"/api/chapters/{CHAPTER}/nodes/alpha.second/simulations"))["run"] is None


def test_building_hides_design_only_finished_and_other_chapters(app: FastAPI) -> None:
    found = service(app, LOG, record("running")).building(CHAPTER)

    assert [(b.step_id, b.state) for b in found] == [(NODE, "running")]
    assert next(s.state for s in found[0].stages if s.name == "scene") == "now"
    assert service(app, LOG, record("running", until="design"), record("done")).building(CHAPTER) == ()
    assert service(app, LOG, record("running")).building(EMPTY_CHAPTER) == ()


def test_building_tells_no_log_no_money_no_reason(app: FastAPI) -> None:
    found = service(app, [*LOG, "✗ секрет", "Потрачено: 1.40"], record("running")).building(CHAPTER)

    assert set(found[0].model_dump()) == {"step_id", "state", "started_at", "stages"}
    assert "секрет" not in found[0].model_dump_json()


def test_queued_run_has_nothing_started(app: FastAPI) -> None:
    waiting = service(app, [], record("queued")).building(CHAPTER)

    assert {s.state for s in waiting[0].stages} == {"wait"}


def test_learner_sees_building_only_in_a_published_course(client: TestClient) -> None:
    error_of(client.get(f"/api/learn/courses/{CHAPTER}/simulations/building"), 404)
    assert data_of(client.get(f"/api/chapters/{CHAPTER}/simulations/building")) == []
