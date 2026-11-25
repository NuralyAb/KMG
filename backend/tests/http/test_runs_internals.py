"""Сбои и края: объект задания, журнал без конца строки, недоступная папка, проверка перед отменой."""

import asyncio
import sys
import time
from pathlib import Path

import pytest
from conftest import FAKE, wait_for
from glava.modules.metrics.reader import read_metrics
from glava.modules.runs import manager as manager_module
from glava.modules.runs import process as process_module
from glava.modules.runs.events import run_events
from glava.modules.runs.manager import RunManager
from glava.modules.runs.process import ProcessTree, child_env
from glava.modules.runs.store import RunRecord, RunStore
from glava.shared.http.errors import ApiError


@pytest.fixture
def manager(tmp_path: Path) -> RunManager:
    return RunManager(tmp_path, (sys.executable, str(FAKE)), 2)


def test_environment_of_server_does_not_leak_into_run() -> None:
    env = child_env({"VIRTUAL_ENV": "server/.venv", "PYTHONPATH": "x", "LLM_MODEL": "sonnet", "PYTHONUTF8": "0"})

    assert env == {"LLM_MODEL": "sonnet", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}


@pytest.mark.skipif(sys.platform != "win32", reason="запасной путь только для Windows")
def test_tree_is_killed_even_without_job_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(pid: int) -> None:
        raise OSError("нельзя")

    monkeypatch.setattr(process_module.Job, "holding", refuse)
    tree = ProcessTree([sys.executable, str(FAKE), "build", "c"], tmp_path, tmp_path / "x.log")
    beat = tmp_path / "work" / "beat_c"
    wait_for(beat.exists)

    tree.kill()
    tree.wait()
    tree.close()
    time.sleep(0.3)
    before = beat.read_text(encoding="utf-8")
    time.sleep(0.4)

    assert beat.read_text(encoding="utf-8") == before


@pytest.mark.skipif(sys.platform != "win32", reason="объект задания только в Windows")
def test_job_of_missing_process_is_an_error() -> None:
    with pytest.raises(OSError):
        process_module.Job.holding(0xFFFFFFF0)


@pytest.mark.skipif(sys.platform != "win32", reason="объект задания только в Windows")
def test_closing_job_kills_descendants_as_after_server_crash(tmp_path: Path) -> None:
    tree = ProcessTree([sys.executable, str(FAKE), "build", "c"], tmp_path, tmp_path / "x.log")
    wait_for((tmp_path / "work" / "beat_c").exists)

    tree.close()

    assert tree.wait() != 0 or not (tmp_path / "work" / "release").exists()


def test_events_show_last_line_without_line_end(manager: RunManager) -> None:
    record = RunRecord("r1", "errata", "c", {}, "done", "2026-01-01T00:00:00+00:00", exit_code=0)
    manager.store.save(record)
    manager.store.log_path("r1").write_bytes("первая\r\nбез конца".encode())
    manager.open()

    async def collect() -> list[str]:
        return [e async for e in run_events(manager, "r1", 0.01)]

    found = asyncio.run(collect())

    assert [e.split("\n")[0] for e in found] == ["event: log", "event: log", "event: state"]
    assert "первая" in found[0] and "\\r" not in found[0] and "без конца" in found[1]


def test_log_folder_that_cannot_be_created_fails_the_run(tmp_path: Path) -> None:
    (tmp_path / "work").write_text("файл вместо папки", encoding="utf-8")
    manager = RunManager(tmp_path, (sys.executable, str(FAKE)), 2)

    record = manager.start("errata", "c")

    assert record.state == "failed"


def test_no_new_runs_while_server_stops(manager: RunManager) -> None:
    manager.close()

    with pytest.raises(ApiError) as caught:
        manager.start("errata", "c")

    assert caught.value.status == 409


def test_process_that_survives_cancel_is_reported(manager: RunManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "STOP_TIMEOUT_S", 0.1)
    run = manager.start("build", "c")

    with monkeypatch.context() as patch:
        patch.setattr(ProcessTree, "kill", lambda self: (_ for _ in ()).throw(OSError("нет прав")))
        with pytest.raises(ApiError) as caught:
            manager.cancel(run.id)

    assert caught.value.status == 500
    monkeypatch.setattr(manager_module, "STOP_TIMEOUT_S", 15)
    assert manager.cancel(run.id).state == "cancelled"


def test_missing_log_is_empty(tmp_path: Path) -> None:
    store = RunStore(tmp_path)

    assert store.tail("none") == [] and store.read_from("none", 0) == b""


@pytest.mark.parametrize("text", [
    b"\xff\xfe\x00bad", b"chapter,stage,nodes,llm_tokens_in,llm_tokens_out,money_usd,person_minutes,mentor_minutes,video_seconds,manual_share\n"
                        b"a,layer,1,1,1,nan,0,0,0,0\na,layer,x,1,1,1,0,0,0,0\n",
])
def test_unreadable_metrics_are_empty(tmp_path: Path, text: bytes) -> None:
    path = tmp_path / "metrics.csv"
    path.write_bytes(text)

    assert read_metrics(path) == []
