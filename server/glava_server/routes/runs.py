"""Запуски конвейера и проверка пакетов."""

from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import StreamingResponse

from glava_server.envelope import Envelope, ok
from glava_server.reviews import get_review, list_reviews, start_review
from glava_server.runs.events import run_events
from glava_server.runs.requests import cli_options, run_args
from glava_server.schemas import Review, Run, RunRequest
from glava_server.services import ServicesDep

router = APIRouter(prefix="/api")


@router.get("/runs")
def list_runs(services: ServicesDep) -> Envelope[list[Run]]:
    return ok([services.runs.store.view(r) for r in services.runs.records()])


@router.post("/runs", status_code=201)
def start_run(request: RunRequest, services: ServicesDep) -> Envelope[Run]:
    args = run_args(request, services.repository)
    return ok(services.runs.store.view(services.runs.start(request.command, request.chapter, cli_options(args), args)))


@router.get("/runs/{run_id}")
def get_run(run_id: str, services: ServicesDep) -> Envelope[Run]:
    return ok(services.runs.store.view(services.runs.get(run_id)))


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str, services: ServicesDep) -> StreamingResponse:
    services.runs.get(run_id)
    stream = run_events(services.runs, run_id, services.settings.poll_seconds)
    return StreamingResponse(stream, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, services: ServicesDep) -> Envelope[Run]:
    return ok(services.runs.store.view(services.runs.cancel(run_id)))


@router.get("/reviews")
def get_reviews(services: ServicesDep) -> Envelope[list[Review]]:
    return ok(list_reviews(services.repository, services.runs))


@router.get("/reviews/{package_id}")
def get_one_review(package_id: str, services: ServicesDep) -> Envelope[Review]:
    return ok(get_review(services.repository, services.runs, package_id))


@router.post("/reviews", status_code=201)
def upload_review(chapter: Annotated[str, Form(max_length=200)], file: UploadFile, services: ServicesDep) -> Envelope[Run]:
    return ok(services.runs.store.view(start_review(services.repository, services.runs, chapter, file.file)))
