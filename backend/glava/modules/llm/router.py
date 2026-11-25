"""Выбор модели."""

from typing import Annotated

from fastapi import APIRouter

from glava.modules.llm.schemas import ModelChoice, ModelSettings
from glava.modules.llm.settings import ModelStore
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter(prefix="/api/settings")
ModelsDep = Annotated[ModelStore, provide(ModelStore)]


@router.get("/model")
def get_model(models: ModelsDep) -> Envelope[ModelSettings]:
    return ok(models.view())


@router.post("/model")
def set_model(request: ModelChoice, models: ModelsDep) -> Envelope[ModelSettings]:
    return ok(models.save(request))
