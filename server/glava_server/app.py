"""Сборка приложения."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from glava_server.config import Settings
from glava_server.errors import install_handlers
from glava_server.guards import Guard
from glava_server.routes import chapters, library, runs, system
from glava_server.services import build_services


def create_app(settings: Settings) -> FastAPI:
    services = build_services(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        services.runs.open()
        yield
        services.runs.close()

    # страницы документации выключены: они тянут скрипты из интернета
    app = FastAPI(title="Глава → курс", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.services = services
    app.add_middleware(Guard, settings=settings)
    install_handlers(app)
    for router in (chapters.router, library.router, runs.router, system.router):
        app.include_router(router)
    return app
