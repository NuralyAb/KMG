import json
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import (
    BASE_URL,
    CHAPTER,
    EMPTY_CHAPTER,
    ORIGIN,
    data_of,
    error_of,
    wait_for,
    write_json,
)
from fastapi.testclient import TestClient
from glava.entrypoints.http.app import create_app
from glava.shared.http.settings import Settings


def start(client: TestClient, command: str = "errata", chapter: str = CHAPTER, **args: Any) -> Any:
    return client.post("/api/runs", json={"command": command, "chapter": chapter, **args}, headers=ORIGIN)


def wait_state(client: TestClient, run_id: str, *states: str) -> dict[str, Any]:
    return wait_for(lambda: (r := data_of(client.get(f"/api/runs/{run_id}")))["state"] in states and r)


def cancel(client: TestClient, run_id: str) -> Any:
    return client.post(f"/api/runs/{run_id}/cancel", headers=ORIGIN)


def add_chapters(root: Path, *names: str) -> None:
    registry = json.loads((root / "chapters.json").read_text(encoding="utf-8"))
    entry = registry["chapters"][CHAPTER]
    write_json(root / "chapters.json", {**registry, "chapters": {**registry["chapters"], **dict.fromkeys(names, entry)}})


def test_run_executes_command_in_root_and_writes_log(client: TestClient, root: Path) -> None:
    created = data_of(start(client), 201)

    done = wait_state(client, created["id"], "done")
    info = json.loads(done["log_tail"][0])

    assert set(created) == {"id", "command", "chapter", "args", "state", "started_at", "finished_at", "exit_code", "log_tail"}
    assert (done["exit_code"], done["command"], done["args"]) == (0, "errata", {})
    assert info == {"argv": ["errata", CHAPTER], "cwd": str(root), "utf8": "1", "venv": None}
    assert done["log_tail"][1] == f"этап errata главы {CHAPTER}"
    assert (root / "work" / "runs" / f"{created['id']}.log").is_file()
    assert done["started_at"] <= done["finished_at"]


def test_failed_command_gives_failed_state(client: TestClient) -> None:
    run = data_of(start(client, "layer"), 201)

    failed = wait_state(client, run["id"], "failed")

    assert failed["exit_code"] == 3
    assert failed["log_tail"][-1] == "узлы не прошли схему"


def test_command_that_cannot_start_gives_failed_state(settings: Settings) -> None:
    broken = Settings(root=settings.root, run_command=("нет_такой_команды_glava",))

    with TestClient(create_app(broken), base_url=BASE_URL) as client:
        failed = wait_state(client, data_of(start(client), 201)["id"], "failed")

    assert failed["exit_code"] is None
    assert "Не удалось запустить" in failed["log_tail"][-1]


def test_arguments_reach_the_command(client: TestClient) -> None:
    layer = data_of(start(client, "layer", limit=2), 201)
    first = wait_state(client, layer["id"], "failed")
    video = data_of(start(client, "video", node="alpha.first", format="wide", template="well_tool"), 201)
    second = wait_state(client, video["id"], "done")

    assert layer["args"] == {"limit": 2}
    assert json.loads(first["log_tail"][0])["argv"] == ["layer", CHAPTER, "--limit", "2"]
    assert json.loads(second["log_tail"][0])["argv"] == ["video", CHAPTER, "--node", "alpha.first", "--format", "wide", "--template", "well_tool"]


def test_simulation_takes_a_node_and_may_stop_after_design(client: TestClient) -> None:
    run = data_of(start(client, "simulation", node="alpha.first", until="design"), 201)
    done = wait_state(client, run["id"], "done")

    assert json.loads(done["log_tail"][0])["argv"] == ["simulation", CHAPTER, "--node", "alpha.first", "--until", "design"]


@pytest.mark.parametrize("payload", [
    {"command": "units"}, {"command": "review"}, {"command": "rm"}, {"command": "layer", "limit": 0}, {"command": "tasks", "limit": 3},
    {"command": "errata", "node": "alpha.first"}, {"command": "video"}, {"command": "video", "node": "alpha.first"},
    {"command": "video", "node": "--help", "template": "well_tool"}, {"command": "video", "node": "alpha.first", "template": "../x"},
    {"command": "video", "node": "alpha.first", "template": "nope"}, {"command": "video", "node": "alpha.first", "template": "well_tool", "format": "4:3"},
    {"command": "simulation"}, {"command": "simulation", "node": "alpha.nope"}, {"command": "simulation", "node": "--help"},
    {"command": "simulation", "node": "alpha.first", "template": "well_tool"}, {"command": "simulation", "node": "alpha.first", "until": "x"},
    {"command": "layer", "until": "design"},
    {"command": "layer", "limt": 2}, {"command": "layer", "chapter": ""},
])
def test_wrong_run_request_is_422_or_404(client: TestClient, payload: dict[str, Any]) -> None:
    response = client.post("/api/runs", json={"chapter": CHAPTER, **payload}, headers=ORIGIN)

    assert response.status_code in (422, 404)
    assert response.json()["success"] is False
    assert data_of(client.get("/api/runs")) == []


def test_run_for_unknown_chapter_or_node_is_404(client: TestClient) -> None:
    error_of(start(client, chapter="nope"), 404)
    error_of(start(client, "video", node="alpha.nope", template="well_tool"), 404)


def test_body_that_is_not_json_is_422(client: TestClient) -> None:
    error_of(client.post("/api/runs", content=b"{", headers={**ORIGIN, "Content-Type": "application/json"}), 422)


def test_second_run_of_busy_chapter_is_409(client: TestClient) -> None:
    first = data_of(start(client, "build"), 201)

    error = error_of(start(client, "errata"), 409)

    assert error["code"] == "conflict"
    assert data_of(client.get("/api/chapters"))[0]["active_run"] == first["id"]


def test_third_process_waits_in_queue(client: TestClient, root: Path) -> None:
    add_chapters(root, "c3", "c4")
    first, second, third, fourth = (data_of(start(client, "build", c), 201) for c in (CHAPTER, EMPTY_CHAPTER, "c3", "c4"))
    wait_state(client, second["id"], "running")

    assert wait_state(client, first["id"], "running")["started_at"]
    assert data_of(client.get(f"/api/runs/{third['id']}"))["state"] == "queued"
    assert [r["id"] for r in data_of(client.get("/api/runs"))] == [fourth["id"], third["id"], second["id"], first["id"]]

    assert data_of(cancel(client, third["id"]))["state"] == "cancelled"
    (root / "work" / "release").touch()
    for run in (first, second, fourth):
        assert wait_state(client, run["id"], "done", "failed")["state"] == "done"
    assert not (root / "work" / "beat_c3").exists()


def test_cancel_kills_whole_process_tree(client: TestClient, root: Path) -> None:
    run = data_of(start(client, "build"), 201)
    beat = root / "work" / f"beat_{CHAPTER}"
    wait_for(beat.exists)

    cancelled = data_of(cancel(client, run["id"]))
    time.sleep(0.3)
    before = beat.read_text(encoding="utf-8")
    time.sleep(0.4)

    assert cancelled["state"] == "cancelled" and cancelled["finished_at"]
    assert beat.read_text(encoding="utf-8") == before
    data_of(start(client, "errata"), 201)


def test_cancel_of_finished_run_is_409(client: TestClient) -> None:
    run = data_of(start(client), 201)
    wait_state(client, run["id"], "done")

    error_of(cancel(client, run["id"]), 409)


@pytest.mark.parametrize("run_id", ["nope", "..", "%2e%2e%2fkey"])
def test_unknown_run_is_404(client: TestClient, run_id: str) -> None:
    error_of(client.get(f"/api/runs/{run_id}"), 404)
    error_of(client.get(f"/api/runs/{run_id}/events"), 404)
    error_of(cancel(client, run_id), 404)


def events(text: str) -> list[tuple[str, dict[str, Any]]]:
    blocks = [b.split("\n") for b in text.strip().split("\n\n") if not b.startswith(":")]
    return [(b[0].removeprefix("event: "), json.loads(b[1].removeprefix("data: "))) for b in blocks]


def test_events_replay_log_and_end_with_final_state(client: TestClient) -> None:
    run = data_of(start(client, "layer"), 201)
    wait_state(client, run["id"], "failed")

    response = client.get(f"/api/runs/{run['id']}/events")

    found = events(response.text)
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [d["line"] for kind, d in found if kind == "log"][1:] == [f"этап layer главы {CHAPTER}", "узлы не прошли схему"]
    assert found[-1] == ("state", {"state": "failed", "exit_code": 3})


def test_events_follow_live_run(client: TestClient, root: Path) -> None:
    run = data_of(start(client, "build"), 201)
    wait_state(client, run["id"], "running")
    (root / "work").joinpath("release").touch()

    found = events(client.get(f"/api/runs/{run['id']}/events").text)

    assert ("log", {"line": "готово"}) in found
    assert found[-1] == ("state", {"state": "done", "exit_code": 0})


def test_restart_marks_unfinished_runs_failed_and_keeps_history(settings: Settings, root: Path) -> None:
    runs = root / "work" / "runs"
    base = {"command": "build", "chapter": CHAPTER, "args": {}, "created_at": "2026-01-01T00:00:00+00:00", "started_at": "2026-01-01T00:00:01+00:00",
            "finished_at": None, "exit_code": None}
    write_json(runs / "r1.json", {**base, "id": "r1", "state": "running"})
    write_json(runs / "r2.json", {**base, "id": "r2", "state": "queued", "created_at": "2026-01-02T00:00:00+00:00"})
    write_json(runs / "r3.json", {**base, "id": "r3", "state": "done", "exit_code": 0, "created_at": "2026-01-03T00:00:00+00:00"})
    (runs / "broken.json").write_text("{", encoding="utf-8")
    write_json(runs / "other.json", {"id": "wrong"})

    with TestClient(create_app(settings), base_url=BASE_URL) as client:
        found = data_of(client.get("/api/runs"))

    assert [(r["id"], r["state"]) for r in found] == [("r3", "done"), ("r2", "failed"), ("r1", "failed")]
    assert found[1]["finished_at"] is not None
    assert json.loads((runs / "r1.json").read_text(encoding="utf-8"))["state"] == "failed"


def test_shutdown_stops_processes_and_fails_queue(settings: Settings, root: Path) -> None:
    add_chapters(root, "c3")
    with TestClient(create_app(settings), base_url=BASE_URL) as client:
        ids = [data_of(start(client, "build", c), 201)["id"] for c in (CHAPTER, EMPTY_CHAPTER, "c3")]
        wait_for((root / "work" / f"beat_{CHAPTER}").exists)

    states = [json.loads((root / "work" / "runs" / f"{i}.json").read_text(encoding="utf-8"))["state"] for i in ids]
    before = (root / "work" / f"beat_{CHAPTER}").read_text(encoding="utf-8")
    time.sleep(0.4)

    assert states == ["failed", "failed", "failed"]
    assert (root / "work" / f"beat_{CHAPTER}").read_text(encoding="utf-8") == before


def test_log_tail_is_short(client: TestClient, root: Path) -> None:
    run = data_of(start(client), 201)
    wait_state(client, run["id"], "done")
    (root / "work" / "runs" / f"{run['id']}.log").write_text("\n".join(f"строка {n}" for n in range(20_000)), encoding="utf-8")

    tail = data_of(client.get(f"/api/runs/{run['id']}"))["log_tail"]

    assert len(tail) == 40 and tail[-1] == "строка 19999"
