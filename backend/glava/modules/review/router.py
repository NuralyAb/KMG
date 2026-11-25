"""Проверка чужого пакета."""

from typing import Annotated

from fastapi import APIRouter, Form, UploadFile

from glava.modules.catalog.api import Repository
from glava.modules.review.schemas import Review
from glava.modules.review.service import get_review, list_reviews, start_review
from glava.modules.runs.api import Run, RunManager
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter(prefix="/api/reviews")
RepositoryDep = Annotated[Repository, provide(Repository)]
RunsDep = Annotated[RunManager, provide(RunManager)]


@router.get("")
def get_reviews(repository: RepositoryDep, runs: RunsDep) -> Envelope[list[Review]]:
    return ok(list_reviews(repository, runs))


@router.get("/{package_id}")
def get_one_review(package_id: str, repository: RepositoryDep, runs: RunsDep) -> Envelope[Review]:
    return ok(get_review(repository, runs, package_id))


@router.post("", status_code=201)
def upload_review(chapter: Annotated[str, Form(max_length=200)], file: UploadFile, repository: RepositoryDep, runs: RunsDep) -> Envelope[Run]:
    return ok(runs.store.view(start_review(repository, runs, chapter, file.file)))
