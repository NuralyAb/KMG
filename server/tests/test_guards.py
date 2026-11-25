from dataclasses import replace

import pytest
from conftest import BASE_URL, CHAPTER, ORIGIN, data_of, error_of
from fastapi import FastAPI
from fastapi.testclient import TestClient

from glava_server.app import create_app
from glava_server.config import Settings

RUN = {"command": "errata", "chapter": CHAPTER}


@pytest.mark.parametrize("headers", [
    {}, {"Origin": "null"}, {"Origin": "http://evil.example"}, {"Origin": "http://127.0.0.1:9999"}, {"Origin": "https://127.0.0.1:5190"},
])
def test_post_from_foreign_origin_is_rejected(client: TestClient, headers: dict[str, str]) -> None:
    error = error_of(client.post("/api/runs", json=RUN, headers=headers), 400)

    assert error["code"] == "bad_origin"
    assert data_of(client.get("/api/runs")) == []


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5190", "http://localhost:5190", BASE_URL])
def test_post_from_own_origin_is_accepted(client: TestClient, origin: str) -> None:
    data_of(client.post("/api/runs", json=RUN, headers={"Origin": origin}), 201)


def test_foreign_host_is_rejected_even_with_matching_origin(client: TestClient) -> None:
    headers = {"Host": "evil.example:8200", "Origin": "http://evil.example:8200"}

    assert error_of(client.get("/api/health", headers=headers), 400)["code"] == "bad_host"
    assert error_of(client.post("/api/runs", json=RUN, headers=headers), 400)["code"] == "bad_host"


@pytest.mark.parametrize("chunked", [False, True])
def test_body_over_limit_gives_413(settings: Settings, chunked: bool) -> None:
    app = create_app(replace(settings, max_body_bytes=1000))
    body = (b"x" * 400 for _ in range(5)) if chunked else b"x" * 2000

    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        response = client.post("/api/runs", content=body, headers={**ORIGIN, "Content-Type": "application/json"})

    assert error_of(response, 413)["code"] == "too_large"


def test_unknown_route_and_wrong_method_return_envelope(client: TestClient) -> None:
    assert error_of(client.get("/api/unknown"), 404)["code"] == "not_found"
    error_of(client.delete("/api/runs", headers=ORIGIN), 400)


def test_unexpected_failure_hides_details(app: FastAPI) -> None:
    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("секрет внутри")

    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        response = client.get("/api/boom")

    assert error_of(response, 500)["code"] == "internal"
    assert "секрет" not in response.text


def test_responses_carry_protective_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["cross-origin-resource-policy"] == "same-origin"
