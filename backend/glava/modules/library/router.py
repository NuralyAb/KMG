"""База знаний: загруженные книги и главы из них."""

from typing import Annotated, Any

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import FileResponse

from glava.modules.library.schemas import (
    ExtractRequest,
    NewChapter,
    Source,
    SourceDetail,
)
from glava.modules.library.service import Library, domain_names
from glava.modules.publishing.api import Publications
from glava.modules.runs.api import Run, RunManager
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok
from glava.shared.http.errors import conflict
from glava.shared.http.settings import Settings

router = APIRouter(prefix="/api")
RunsDep = Annotated[RunManager, provide(RunManager)]
LibraryDep = Annotated[Library, provide(Library)]
PublicationsDep = Annotated[Publications, provide(Publications)]
SettingsDep = Annotated[Settings, provide(Settings)]
INLINE = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@router.get("/library")
def list_sources(library: LibraryDep) -> Envelope[list[Source]]:
    return ok(library.sources())


@router.post("/library", status_code=201)
def upload_source(file: UploadFile, library: LibraryDep, vision: Annotated[bool, Form()] = False) -> Envelope[Source]:
    return ok(library.add(file.filename, file.file, vision))


@router.get("/library/{source_id}")
def get_source(source_id: str, library: LibraryDep) -> Envelope[SourceDetail]:
    return ok(library.detail(source_id))


@router.get("/library/{source_id}/pages/{number}")
def get_page(source_id: str, number: int, library: LibraryDep) -> Envelope[dict[str, Any]]:
    return ok({"page": number, "text": library.page_text(source_id, number)})


@router.get("/library/{source_id}/pages/{number}/image")
def get_page_image(source_id: str, number: int, library: LibraryDep) -> FileResponse:
    return FileResponse(library.page_image(source_id, number), media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.get("/library/{source_id}/original")
def get_original(source_id: str, library: LibraryDep) -> FileResponse:
    """PDF и картинки открываются рядом с текстом; остальное браузер только скачивает."""
    file, _ = library.original(source_id)
    media = INLINE.get(file.suffix.lower())
    headers = {"Content-Security-Policy": "sandbox; default-src 'none'"} if media is None else {}
    return FileResponse(file, media_type=media or "application/octet-stream", filename=None if media else file.name, headers=headers)


@router.post("/library/{source_id}/extract", status_code=201)
def extract_source(source_id: str, request: ExtractRequest, runs: RunsDep, library: LibraryDep) -> Envelope[Run]:
    return ok(runs.store.view(library.extract(source_id, request.vision)))


@router.post("/library/{source_id}/chapters", status_code=201)
def create_chapter(source_id: str, request: NewChapter, library: LibraryDep, settings: SettingsDep) -> Envelope[dict[str, str]]:
    return ok({"id": library.add_chapter(source_id, request, domain_names(settings.root))})


@router.delete("/library/{source_id}")
def delete_source(source_id: str, library: LibraryDep) -> Envelope[dict[str, str]]:
    library.remove(source_id)
    return ok({"id": source_id})


@router.delete("/library/chapters/{chapter_id}")
def delete_chapter(chapter_id: str, library: LibraryDep, publications: PublicationsDep) -> Envelope[dict[str, str]]:
    if publications.published_at(chapter_id):
        raise conflict("Курс опубликован: сначала снимите его с публикации")
    library.remove_chapter(chapter_id)
    return ok({"id": chapter_id})


@router.get("/domains")
def list_domains(settings: SettingsDep) -> Envelope[list[str]]:
    return ok(domain_names(settings.root))
