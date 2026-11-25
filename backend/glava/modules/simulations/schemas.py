"""Симуляторы шага: ответы."""

from typing import Literal

from glava.modules.simulations.progress import StageState
from glava.shared.http.dto import Model


class SimulationStage(Model):
    name: str
    state: StageState


class Building(Model):
    """Что видно в курсе, пока агент работает: ни журнала, ни расхода здесь нет."""

    step_id: str
    state: Literal["queued", "running"]
    started_at: str | None
    stages: tuple[SimulationStage, ...]


class SimulationRun(Model):
    id: str
    state: Literal["queued", "running", "done", "failed", "cancelled"]
    is_design_only: bool
    started_at: str | None
    finished_at: str | None
    stages: tuple[SimulationStage, ...]
    retry: int
    reason: str | None


class Scene(Model):
    id: str
    title: str
    goal: str
    label: str
    poster_url: str | None
    player_url: str


class NodeSimulations(Model):
    scenes: tuple[Scene, ...]
    run: SimulationRun | None
