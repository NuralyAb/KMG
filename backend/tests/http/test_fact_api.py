"""Живой факт через HTTP: проба ничего не пишет, правка пишет слой и журнал и запускает пересборку."""

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CHAPTER, ORIGIN, wait_for
from fastapi.testclient import TestClient

URL = f"/api/chapters/{CHAPTER}/fact"
EDIT = {"claim_id": "alpha.n#c1", "text": "Чёрный сланец не плотный", "minutes": 2.5, "reason": "опечатка книги"}


@pytest.fixture
def built(root: Path) -> Path:
    """Курс собран по нынешнему слою."""
    layer = json.loads((root / "work" / CHAPTER / "layer.json").read_text(encoding="utf-8"))
    (root / "out" / CHAPTER / "data.js").write_text("window.COURSE=" + json.dumps({"id": CHAPTER, "steps": layer["nodes"]}, ensure_ascii=False) + ";\n", encoding="utf-8")
    return root


def post(client: TestClient, path: str, body: dict[str, Any]) -> Any:
    return client.post(f"{URL}/{path}", json=body, headers=ORIGIN)


def test_nothing_is_pending_after_a_build(client: TestClient, built: Path) -> None:
    assert client.get(URL).json()["data"]["changes"] == []


def test_unbuilt_course_has_nothing_to_compare_with(client: TestClient) -> None:
    assert client.get(URL).status_code == 409


def test_probe_shows_the_conflict_and_writes_nothing(client: TestClient, built: Path) -> None:
    before = (built / "work" / CHAPTER / "layer.json").read_bytes()
    data = post(client, "probe", {"claim_id": "alpha.n#c1", "text": EDIT["text"]}).json()["data"]
    assert data["changes"][0]["conflicts"] == ["negation"] and data["changes"][0]["is_serious"]
    assert [s["id"] for s in data["steps"]] == ["alpha.first"]
    assert (built / "work" / CHAPTER / "layer.json").read_bytes() == before


def test_serious_edit_needs_a_human_word(client: TestClient, built: Path) -> None:
    reply = post(client, "apply", EDIT)
    assert reply.status_code == 409 and "цитате" in reply.json()["error"]["message"]
    assert not (built / "manual_edits.csv").exists()


def test_accepted_edit_is_written_journaled_and_started(client: TestClient, built: Path) -> None:
    reply = post(client, "apply", {**EDIT, "accept": True})
    assert reply.status_code == 201 and reply.json()["data"]["command"] == "fact"
    layer = json.loads((built / "work" / CHAPTER / "layer.json").read_text(encoding="utf-8"))
    assert layer["nodes"][0]["claims"][0]["text"] == EDIT["text"]
    with (built / "manual_edits.csv").open(encoding="utf-8", newline="") as file:
        (row,) = csv.DictReader(file)
    assert (row["chapter"], row["person_minutes"], row["reason"]) == (CHAPTER, "2.5", "опечатка книги")
    run = reply.json()["data"]["id"]
    wait_for(lambda: client.get(f"/api/runs/{run}").json()["data"]["state"] not in ("queued", "running"))


@pytest.mark.parametrize(("body", "status"), [
    ({**EDIT, "claim_id": "alpha.n#c99"}, 404), ({**EDIT, "text": "Чёрный сланец плотный"}, 422), ({**EDIT, "minutes": 0}, 422), ({**EDIT, "reason": ""}, 422), ({**EDIT, "x": 1}, 422)])
def test_bad_edits(client: TestClient, built: Path, body: dict[str, Any], status: int) -> None:
    assert post(client, "apply", body).status_code == status


def test_unknown_chapter(client: TestClient) -> None:
    assert client.get("/api/chapters/nope/fact").status_code == 404
