"""Книги и добавление глав."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from glava.modules.books.service import MAX_MD, BookShelf, card
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter(prefix="/api/books")
Row = dict[str, Any]
BooksDep = Annotated[BookShelf, provide(BookShelf)]


class NewChapter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    pages: list[Annotated[list[int], Field(min_length=2, max_length=2)]] = Field(min_length=1, max_length=50)
    domain: str = Field(default="geology", max_length=100)


@router.get("")
def list_books(books: BooksDep) -> Envelope[list[Row]]:
    return ok([card(b) for b in books.books()])


@router.post("", status_code=201)
def upload_book(file: UploadFile, books: BooksDep, pdf: UploadFile | None = None) -> Envelope[Row]:
    md = file.file.read(MAX_MD + 1)
    return ok(card(books.add(file.filename or "", md, pdf.file if pdf else None)))


@router.get("/{book_id}")
def get_book(book_id: str, books: BooksDep) -> Envelope[Row]:
    book = books.book(book_id)
    sections, pages = books.sections(book)
    domains = books.domains()
    return ok({**card(book), "sections": [asdict(s) for s in sections], "first_page": pages[0] if pages else None,
               "last_page": pages[-1] if pages else None, "domains": domains})


@router.post("/{book_id}/chapters", status_code=201)
def create_chapter(book_id: str, body: NewChapter, books: BooksDep) -> Envelope[Row]:
    chapter_id = books.create_chapter(book_id, body.title, [(a, b) for a, b in body.pages], body.domain)
    return ok({"id": chapter_id})
