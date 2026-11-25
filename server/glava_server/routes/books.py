"""Книги и добавление глав."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from glava_server.books import MAX_MD, Library, card
from glava_server.envelope import Envelope, ok
from glava_server.services import ServicesDep

router = APIRouter(prefix="/api/books")
Row = dict[str, Any]


class NewChapter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    pages: list[Annotated[list[int], Field(min_length=2, max_length=2)]] = Field(min_length=1, max_length=50)
    domain: str = Field(default="geology", max_length=100)


def _library(services: ServicesDep) -> Library:
    return Library(services.settings.root)


@router.get("")
def list_books(services: ServicesDep) -> Envelope[list[Row]]:
    return ok([card(b) for b in _library(services).books()])


@router.post("", status_code=201)
def upload_book(file: UploadFile, services: ServicesDep, pdf: UploadFile | None = None) -> Envelope[Row]:
    md = file.file.read(MAX_MD + 1)
    return ok(card(_library(services).add(file.filename or "", md, pdf.file if pdf else None)))


@router.get("/{book_id}")
def get_book(book_id: str, services: ServicesDep) -> Envelope[Row]:
    library = _library(services)
    book = library.book(book_id)
    sections, pages = library.sections(book)
    domains = sorted(p.name for p in (services.settings.root / "domain").iterdir() if p.is_dir()) if (services.settings.root / "domain").is_dir() else []
    return ok({**card(book), "sections": [asdict(s) for s in sections], "first_page": pages[0] if pages else None,
               "last_page": pages[-1] if pages else None, "domains": domains})


@router.post("/{book_id}/chapters", status_code=201)
def create_chapter(book_id: str, body: NewChapter, services: ServicesDep) -> Envelope[Row]:
    chapter_id = _library(services).create_chapter(book_id, body.title, [(a, b) for a, b in body.pages], body.domain)
    return ok({"id": chapter_id})
