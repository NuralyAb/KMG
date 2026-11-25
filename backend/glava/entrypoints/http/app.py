"""Сборка приложения: единственное место, которое знает про все модули сразу."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from glava.entrypoints.http.chapter_status import LiveChapterStatus
from glava.entrypoints.http.guards import Guard
from glava.modules.access import module as access
from glava.modules.access.api import Access, AccessGuard
from glava.modules.books import module as books
from glava.modules.catalog import module as catalog
from glava.modules.catalog.api import ChapterStatus
from glava.modules.library import module as library
from glava.modules.llm import module as llm
from glava.modules.publishing import module as publishing
from glava.modules.publishing.api import Publications
from glava.modules.review import module as review
from glava.modules.runs import module as runs
from glava.modules.runs.api import RunManager
from glava.modules.simulations import module as simulations
from glava.modules.system import module as system
from glava.shared.http.container import Container
from glava.shared.http.errors import install_handlers
from glava.shared.http.settings import Settings

# порядок сборки: модуль стоит после тех, от чьих сервисов зависит
MODULES = (access, llm, catalog, runs, publishing, library, books, review, simulations, system)


def build_container(settings: Settings) -> Container:
    container = Container()
    container.add(Settings, settings)
    for module in MODULES:
        module.install(container, settings)
    container.add(ChapterStatus, LiveChapterStatus(container.get(RunManager), container.get(Publications)))
    return container


def create_app(settings: Settings) -> FastAPI:
    container = build_container(settings)
    manager = container.get(RunManager)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        manager.open()
        yield
        manager.close()

    # страницы документации выключены: они тянут скрипты из интернета
    app = FastAPI(title="Глава → курс", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.container = container
    # добавленное последним срабатывает первым: сначала свой ли это хост, потом кто пришёл
    app.add_middleware(AccessGuard, access=container.get(Access))
    app.add_middleware(Guard, settings=settings)
    install_handlers(app)
    for module in MODULES:
        app.include_router(module.router)
    return app
