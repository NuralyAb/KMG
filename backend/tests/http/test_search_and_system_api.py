from pathlib import Path

import pytest
from conftest import CHAPTER, EMPTY_CHAPTER, data_of, error_of
from fastapi.testclient import TestClient
from glava.modules.system.health import health


@pytest.mark.parametrize("query", ["чёрный", "ЧЕРНЫЙ", "  черный  сланец ", "сланец плотный"])
def test_search_ignores_case_yo_and_spacing(client: TestClient, query: str) -> None:
    response = client.get("/api/search", params={"q": query})

    assert data_of(response) == [{"chapter": CHAPTER, "node_id": "alpha.first", "node_title": "Узел first", "claim_id": "alpha.n#c1",
                                  "text": "Чёрный сланец плотный", "quote": "сланец чёрный и плотный", "page_pdf": 10}]
    assert response.json()["meta"] == {"total": 1, "page": 1, "limit": 20}


def test_search_pages_results(client: TestClient) -> None:
    first = client.get("/api/search", params={"q": "ни", "limit": 1, "page": 1})
    second = client.get("/api/search", params={"q": "ли", "limit": 1, "page": 9})

    assert len(data_of(first)) == 1
    assert data_of(second) == []


def test_search_in_one_chapter(client: TestClient) -> None:
    assert data_of(client.get("/api/search", params={"q": "глина", "chapter": EMPTY_CHAPTER})) == []
    assert len(data_of(client.get("/api/search", params={"q": "глина", "chapter": CHAPTER}))) == 1
    error_of(client.get("/api/search", params={"q": "глина", "chapter": "nope"}), 404)


@pytest.mark.parametrize("params", [{"q": "а"}, {"q": "  а "}, {}, {"q": "глина", "page": 0}, {"q": "глина", "limit": 101}, {"q": "я" * 201}])
def test_wrong_search_parameters_are_422(client: TestClient, params: dict[str, object]) -> None:
    error_of(client.get("/api/search", params=params), 422)


def test_metrics_have_rows_and_totals(client: TestClient) -> None:
    response = client.get("/api/metrics")

    assert len(data_of(response)) == 3
    assert data_of(response)[0] == {"chapter": CHAPTER, "stage": "layer", "nodes": 3, "llm_tokens_in": 1000, "llm_tokens_out": 200, "money_usd": 1.25,
                                    "person_minutes": 0.0, "mentor_minutes": 0.0, "video_seconds": 0.0, "manual_share": 0.0}
    assert response.json()["meta"] == {"cost_usd": 2.0, "tokens_in": 1510, "tokens_out": 320}


def test_health_route_answers(client: TestClient) -> None:
    body = data_of(client.get("/api/health"))

    assert body["status"] == "ok"
    assert set(body) == {"status", "provider", "model", "claude_found", "ffmpeg_found"}


def test_health_reads_provider_from_environment(tmp_path: Path) -> None:
    exe = tmp_path / "claude.exe"
    exe.write_bytes(b"")

    found = health({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m", "CLAUDE_EXE": str(exe)}, which=lambda _: None)
    missing = health({"CLAUDE_EXE": str(tmp_path / "нет.exe")}, which=lambda _: None)
    by_path = health({}, which=lambda name: name)

    assert (found.provider, found.model, found.claude_found, found.ffmpeg_found) == ("anthropic", "m", True, False)
    assert (missing.provider, missing.model, missing.claude_found) == ("claude_code", "sonnet", False)
    assert by_path.claude_found and by_path.ffmpeg_found
