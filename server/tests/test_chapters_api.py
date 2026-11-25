import os
from pathlib import Path

import pytest
from conftest import CHAPTER, EMPTY_CHAPTER, T0, data_of, error_of, write_json
from fastapi.testclient import TestClient

BASE = f"/api/chapters/{CHAPTER}"


def test_card_collects_counts_cost_and_stages(client: TestClient) -> None:
    card = data_of(client.get("/api/chapters"))[0]

    assert card["id"] == CHAPTER
    assert card["pages"] == [10, 11, 12, 20, 21]
    assert card["counts"] == {"nodes": 3, "claims": 4, "tasks": 3, "illustrations": 1, "errata": 2, "units": 3, "units_covered": 2, "videos": 1}
    assert card["issues"] == 3
    assert (card["cost_usd"], card["tokens_in"], card["tokens_out"]) == (1.5, 1500, 300)
    assert card["course_url"] == f"/course/{CHAPTER}/index.html"
    assert card["active_run"] is None
    assert set(card) == {"id", "title", "book", "domain", "pages", "counts", "issues", "stages", "cost_usd", "tokens_in", "tokens_out", "course_url",
                         "active_run", "published_at"}


def test_stage_older_than_previous_is_stale(client: TestClient) -> None:
    stages = data_of(client.get("/api/chapters"))[0]["stages"]

    # рисунки в наборе старше заданий
    assert {s["name"]: s["state"] for s in stages} == {"errata": "ready", "layer": "ready", "routing": "ready", "tasks": "ready",
                                                       "illustrations": "stale", "course": "ready"}
    assert [s["name"] for s in stages] == ["errata", "layer", "routing", "tasks", "illustrations", "course"]
    assert stages[0]["updated_at"].startswith("2025-10-09T")


def test_stage_is_compared_with_nearest_existing_previous_stage(client: TestClient, root: Path) -> None:
    (root / "work" / CHAPTER / "routing.json").unlink()
    layer = root / "work" / CHAPTER / "layer.json"
    os.utime(layer, (T0 + 1000, T0 + 1000))

    stages = {s["name"]: s["state"] for s in data_of(client.get("/api/chapters"))[0]["stages"]}

    assert (stages["routing"], stages["tasks"]) == ("missing", "stale")


def test_chapter_without_data_has_missing_stages(client: TestClient) -> None:
    card = data_of(client.get("/api/chapters"))[1]

    assert card["id"] == EMPTY_CHAPTER
    assert {s["state"] for s in card["stages"]} == {"missing"}
    assert all(s["updated_at"] is None for s in card["stages"])
    assert card["course_url"] is None
    assert set(card["counts"].values()) == {0}


@pytest.mark.parametrize("path", ["", "/coverage", "/errata", "/routing", "/tasks", "/illustrations", "/videos"])
def test_every_route_works_for_chapter_without_data(client: TestClient, path: str) -> None:
    data = data_of(client.get(f"/api/chapters/{EMPTY_CHAPTER}{path}"))

    assert data == [] or data["parts"] == []


@pytest.mark.parametrize("chapter_id", ["nope", "..%2F..", "%2e%2e", "-x"])
def test_unknown_chapter_is_404(client: TestClient, chapter_id: str) -> None:
    assert error_of(client.get(f"/api/chapters/{chapter_id}"), 404)["code"] == "not_found"


def test_detail_lists_parts_with_node_rows(client: TestClient) -> None:
    parts = data_of(client.get(BASE))["parts"]

    assert [p["title"] for p in parts] == ["Часть 1", "Вне частей"]
    assert [n["id"] for n in parts[0]["nodes"]] == ["alpha.first", "alpha.second"]
    assert parts[0]["nodes"][0] == {"id": "alpha.first", "order": 1, "title": "Узел first", "short_title": "first",
                                    "difficulty": {"primary": "Пр", "secondary": None}, "threshold": False, "pages": [10], "claims": 2, "tasks": 2,
                                    "format": "карточки", "needs_scan": 2}
    assert parts[0]["nodes"][1]["format"] is None


def test_node_detail_joins_route_tasks_pictures_and_neighbours(client: TestClient) -> None:
    detail = data_of(client.get(f"{BASE}/nodes/alpha.first"))
    last = data_of(client.get(f"{BASE}/nodes/alpha.third"))

    assert detail["node"]["id"] == "alpha.first" and len(detail["node"]["claims"]) == 2
    assert detail["route"]["format"] == "карточки"
    assert [t["id"] for t in detail["tasks"]] == ["t1", "t2"]
    assert detail["illustrations"][0]["url"] == f"/course/{CHAPTER}/pictures/first_1.svg"
    assert (detail["prev"], detail["next"]) == (None, "alpha.second")
    assert (last["prev"], last["next"], last["route"]) == ("alpha.second", None, None)


@pytest.mark.parametrize("node_id", ["alpha.nope", "alpha.first.", "%2e%2e%2fkey"])
def test_unknown_node_is_404(client: TestClient, node_id: str) -> None:
    error_of(client.get(f"{BASE}/nodes/{node_id}"), 404)


def test_coverage_can_show_only_uncovered_rows(client: TestClient) -> None:
    everything = client.get(f"{BASE}/coverage")
    uncovered = client.get(f"{BASE}/coverage?uncovered=1")

    assert len(data_of(everything)) == 3
    assert [r["unit_id"] for r in data_of(uncovered)] == ["p010.02"]
    assert everything.json()["meta"] == uncovered.json()["meta"] == {"total": 3, "covered": 2, "skipped": 1}


def test_wrong_coverage_filter_is_422(client: TestClient) -> None:
    error = error_of(client.get(f"{BASE}/coverage?uncovered=5"), 422)

    assert "uncovered" in error["message"]


def test_errata_counts_kinds(client: TestClient) -> None:
    response = client.get(f"{BASE}/errata")

    assert len(data_of(response)) == 2
    assert response.json()["meta"] == {"recognition": 1, "suspect": 1}


def test_routing_returns_routes(client: TestClient) -> None:
    assert data_of(client.get(f"{BASE}/routing"))[0]["node_id"] == "alpha.first"


def test_tasks_are_filtered_by_type_and_node(client: TestClient) -> None:
    everything = client.get(f"{BASE}/tasks?type=&node=")
    single = client.get(f"{BASE}/tasks?type=single&node=alpha.first")

    assert everything.json()["meta"] == {"total": 3, "by_type": {"single": 2, "calc": 1}}
    assert [t["id"] for t in data_of(single)] == ["t1"]
    assert single.json()["meta"] == {"total": 1, "by_type": {"single": 1, "calc": 1}}


def test_unknown_task_type_is_422(client: TestClient) -> None:
    error_of(client.get(f"{BASE}/tasks?type=essay"), 422)


def test_illustrations_get_url_and_bad_paths_get_none(client: TestClient, root: Path) -> None:
    write_json(root / "work" / CHAPTER / "illustrations.json", {"illustrations": [
        {"id": "a", "file": "pictures/рис 1.svg"}, {"id": "b", "file": "../../key.json"}, {"id": "c"}]})

    rows = data_of(client.get(f"{BASE}/illustrations"))

    assert rows[0]["url"] == f"/course/{CHAPTER}/pictures/%D1%80%D0%B8%D1%81%201.svg"
    assert rows[1]["url"] is None and rows[2]["url"] is None


def test_videos_join_passport_and_skip_unfinished(client: TestClient) -> None:
    videos = data_of(client.get(f"{BASE}/videos"))

    assert len(videos) == 1
    assert {k: v for k, v in videos[0].items() if k != "passport"} == {
        "id": "v1", "chapter": CHAPTER, "title": "Узел first", "format": "16:9", "duration_s": 61.5, "url": f"/course/{CHAPTER}/videos/v1.mp4",
        "subtitles_url": f"/course/{CHAPTER}/videos/v1.srt", "problems": ["тихо"]}
    assert videos[0]["passport"]["video_id"] == "v1"


def test_half_written_layer_does_not_break_the_list(client: TestClient, root: Path) -> None:
    (root / "work" / CHAPTER / "layer.json").write_text('{"nodes": [{"id"', encoding="utf-8")

    card = data_of(client.get("/api/chapters"))[0]

    assert card["counts"]["nodes"] == 0


def test_foreign_shapes_inside_files_do_not_break_answers(client: TestClient, root: Path) -> None:
    write_json(root / "work" / CHAPTER / "layer.json", {"nodes": [{"id": "alpha.odd", "claims": None, "difficulty": "Пр"}, "строка", {"no": "id"}],
                                                        "parts": [{"nodes": ["alpha.odd", 5]}, 7]})
    write_json(root / "work" / CHAPTER / "layer_report.json", {"issues": ["не словарь"]})

    detail = data_of(client.get(BASE))

    assert detail["parts"][0]["nodes"][0]["id"] == "alpha.odd"
    assert detail["issues"] == 0
