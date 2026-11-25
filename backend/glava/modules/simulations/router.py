"""Симуляторы шага и ход работы агента."""

from typing import Annotated

from fastapi import APIRouter

from glava.modules.catalog.api import Repository
from glava.modules.publishing.api import Publications
from glava.modules.simulations.schemas import Building, NodeSimulations
from glava.modules.simulations.service import Simulations
from glava.shared.http.container import provide
from glava.shared.http.envelope import Envelope, ok

router = APIRouter()
RepositoryDep = Annotated[Repository, provide(Repository)]
PublicationsDep = Annotated[Publications, provide(Publications)]
SimulationsDep = Annotated[Simulations, provide(Simulations)]


@router.get("/api/chapters/{chapter_id}/nodes/{node_id}/simulations")
def get_node_simulations(chapter_id: str, node_id: str, repository: RepositoryDep, simulations: SimulationsDep) -> Envelope[NodeSimulations]:
    return ok(simulations.node(repository.chapter(chapter_id).id, node_id))


@router.get("/api/chapters/{chapter_id}/simulations/building")
def get_building(chapter_id: str, repository: RepositoryDep, simulations: SimulationsDep) -> Envelope[tuple[Building, ...]]:
    return ok(simulations.building(repository.chapter(chapter_id).id))


@router.get("/api/learn/courses/{course_id}/simulations/building")
def get_learn_building(course_id: str, publications: PublicationsDep, simulations: SimulationsDep) -> Envelope[tuple[Building, ...]]:
    return ok(simulations.building(publications.course(course_id).id))
