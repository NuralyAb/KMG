"""Живой факт."""

from typing import Annotated

from fastapi import APIRouter

from glava.modules.impact.schemas import FactEdit, FactProbe, FactReport
from glava.modules.impact.service import Facts
from glava.modules.runs.api import Run, RunManager
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter(prefix="/api/chapters/{chapter_id}/fact")
FactsDep = Annotated[Facts, provide(Facts)]
RunsDep = Annotated[RunManager, provide(RunManager)]


@router.get("")
def get_pending(chapter_id: str, facts: FactsDep) -> Envelope[FactReport]:
    return ok(FactReport.model_validate(facts.pending(chapter_id)))


@router.post("/probe")
def probe(chapter_id: str, request: FactProbe, facts: FactsDep) -> Envelope[FactReport]:
    return ok(FactReport.model_validate(facts.probe(chapter_id, request.claim_id, request.text)))


@router.post("/apply", status_code=201)
def apply(chapter_id: str, request: FactEdit, facts: FactsDep, runs: RunsDep) -> Envelope[Run]:
    return ok(runs.store.view(facts.apply(chapter_id, request)))
