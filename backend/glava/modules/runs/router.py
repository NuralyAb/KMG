"""Запуски конвейера."""

from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from glava.modules.catalog.api import Repository
from glava.modules.runs.events import run_events
from glava.modules.runs.manager import RunManager
from glava.modules.runs.requests import cli_options, run_args
from glava.modules.runs.schemas import Run, RunRequest
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok
from glava.shared.http.settings import Settings

router = APIRouter(prefix="/api/runs")
RepositoryDep = Annotated[Repository, provide(Repository)]
RunsDep = Annotated[RunManager, provide(RunManager)]
SettingsDep = Annotated[Settings, provide(Settings)]


@router.get("")
def list_runs(runs: RunsDep) -> Envelope[list[Run]]:
    return ok([runs.store.view(r) for r in runs.records()])


@router.post("", status_code=201)
def start_run(request: RunRequest, repository: RepositoryDep, runs: RunsDep) -> Envelope[Run]:
    args = run_args(request, repository)
    return ok(runs.store.view(runs.start(request.command, request.chapter, cli_options(args), args)))


@router.get("/{run_id}")
def get_run(run_id: str, runs: RunsDep) -> Envelope[Run]:
    return ok(runs.store.view(runs.get(run_id)))


@router.get("/{run_id}/events")
def get_run_events(run_id: str, runs: RunsDep, settings: SettingsDep) -> StreamingResponse:
    runs.get(run_id)
    stream = run_events(runs, run_id, settings.poll_seconds)
    return StreamingResponse(stream, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, runs: RunsDep) -> Envelope[Run]:
    return ok(runs.store.view(runs.cancel(run_id)))
