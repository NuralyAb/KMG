"""База знаний и выбор модели."""

from typing import Annotated, Any

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import FileResponse

from glava_server.envelope import Envelope, ok
from glava_server.library import domain_names
from glava_server.schemas import ExtractRequest, ModelChoice, ModelSettings, NewChapter, Run, Source, SourceDetail
from glava_server.services import ServicesDep

router = APIRouter(prefix="/api")
INLINE = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@router.get("/library")
def list_sources(services: ServicesDep) -> Envelope[list[Source]]:
    return ok(services.library.sources())


@router.post("/library", status_code=201)
def upload_source(file: UploadFile, services: ServicesDep, vision: Annotated[bool, Form()] = False) -> Envelope[Source]:
    return ok(services.library.add(file.filename, file.file, vision))


@router.get("/library/{source_id}")
def get_source(source_id: str, services: ServicesDep) -> Envelope[SourceDetail]:
    return ok(services.library.detail(source_id))


@router.get("/library/{source_id}/pages/{number}")
def get_page(source_id: str, number: int, services: ServicesDep) -> Envelope[dict[str, Any]]:
    return ok({"page": number, "text": services.library.page_text(source_id, number)})


@router.get("/library/{source_id}/pages/{number}/image")
def get_page_image(source_id: str, number: int, services: ServicesDep) -> FileResponse:
    return FileResponse(services.library.page_image(source_id, number), media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.get("/library/{source_id}/original")
def get_original(source_id: str, services: ServicesDep) -> FileResponse:
    """PDF и картинки открываются рядом с текстом; остальное браузер только скачивает."""
    file, _ = services.library.original(source_id)
    media = INLINE.get(file.suffix.lower())
    headers = {"Content-Security-Policy": "sandbox; default-src 'none'"} if media is None else {}
    return FileResponse(file, media_type=media or "application/octet-stream", filename=None if media else file.name, headers=headers)


@router.post("/library/{source_id}/extract", status_code=201)
def extract_source(source_id: str, request: ExtractRequest, services: ServicesDep) -> Envelope[Run]:
    return ok(services.runs.store.view(services.library.extract(source_id, request.vision)))


@router.post("/library/{source_id}/chapters", status_code=201)
def create_chapter(source_id: str, request: NewChapter, services: ServicesDep) -> Envelope[dict[str, str]]:
    return ok({"id": services.library.add_chapter(source_id, request, domain_names(services.settings.root))})


@router.delete("/library/{source_id}")
def delete_source(source_id: str, services: ServicesDep) -> Envelope[dict[str, str]]:
    services.library.remove(source_id)
    return ok({"id": source_id})


@router.delete("/library/chapters/{chapter_id}")
def delete_chapter(chapter_id: str, services: ServicesDep) -> Envelope[dict[str, str]]:
    services.library.remove_chapter(chapter_id)
    return ok({"id": chapter_id})


@router.get("/domains")
def list_domains(services: ServicesDep) -> Envelope[list[str]]:
    return ok(domain_names(services.settings.root))


@router.get("/settings/model")
def get_model(services: ServicesDep) -> Envelope[ModelSettings]:
    return ok(services.models.view())


@router.post("/settings/model")
def set_model(request: ModelChoice, services: ServicesDep) -> Envelope[ModelSettings]:
    return ok(services.models.save(request))
