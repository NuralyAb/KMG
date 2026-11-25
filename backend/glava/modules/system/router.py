"""Состояние приложения."""

from typing import Annotated

from fastapi import APIRouter

from glava.modules.llm.api import ModelStore
from glava.modules.system.health import health
from glava.modules.system.schemas import Health
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter(prefix="/api")
ModelsDep = Annotated[ModelStore, provide(ModelStore)]


@router.get("/health")
def get_health(models: ModelsDep) -> Envelope[Health]:
    return ok(health(models.env()))
