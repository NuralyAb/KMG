"""Готовые сцены собранного курса и запуски агента."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from glava.modules.catalog.api import Repository
from glava.modules.runs.api import RunManager, RunRecord
from glava.modules.simulations.progress import STAGES, Progress, read_progress
from glava.modules.simulations.schemas import Building, NodeSimulations, Scene, SimulationRun, SimulationStage
from glava.shared.http.errors import not_found
from glava.shared.identifiers import is_safe_id

PREFIX = "globalThis.SIM_SCENES="
PLAYER = "assets/sim/player.html"


class Simulations:
    def __init__(self, repository: Repository, runs: RunManager) -> None:
        self._repository = repository
        self._runs = runs

    def node(self, chapter_id: str, node_id: str) -> NodeSimulations:
        if not any(n.get("id") == node_id for n in self._repository.nodes(chapter_id)):
            raise not_found("Такого узла нет")
        # последний запуск по шагу: рядом со сценой видно и то, чем он кончился
        latest = next((r for r in self._runs.records() if _is_for(r, chapter_id) and r.args.get("node") == node_id), None)
        return NodeSimulations(scenes=self._scenes(chapter_id, node_id), run=self._run(latest) if latest else None)

    def building(self, chapter_id: str) -> tuple[Building, ...]:
        """Симуляторы, которые строятся сейчас. Запуск «только замысел» сцены не даёт и сюда не входит."""
        return tuple(
            Building(step_id=str(r.args.get("node")), state=r.state, started_at=r.started_at, stages=_stages(self._progress(r)))
            for r in self._runs.records() if _is_for(r, chapter_id) and r.is_active and not _is_design_only(r)
        )

    def _scenes(self, chapter_id: str, node_id: str) -> tuple[Scene, ...]:
        """Только сцены, которые уже лежат в собранном курсе: их и откроет проигрыватель."""
        folder = self._repository.course_folder(chapter_id)
        if not (folder / PLAYER).is_file():
            return ()
        root = f"/course/{quote(chapter_id, safe='')}"
        found = []
        for name, scene in _published(folder / "simulations.js").items():
            if not is_safe_id(name) or not isinstance(scene, dict) or scene.get("node_id") != node_id:
                continue
            has_poster = (folder / "simulations" / f"{name}.webp").is_file()
            found.append(Scene(
                id=name, title=str(scene.get("title") or name), goal=str(scene.get("goal") or scene.get("intro") or ""),
                label=str(scene.get("provenance") or ""), poster_url=f"{root}/simulations/{quote(name)}.webp" if has_poster else None,
                player_url=f"{root}/{PLAYER}#{quote(name)}",
            ))
        return tuple(found)

    def _progress(self, record: RunRecord) -> Progress:
        return read_progress(self._runs.log_lines(record.id), record.state == "running")

    def _run(self, record: RunRecord) -> SimulationRun:
        progress = self._progress(record)
        return SimulationRun(
            id=record.id, state=record.state, is_design_only=_is_design_only(record), started_at=record.started_at,
            finished_at=record.finished_at, stages=_stages(progress, _is_design_only(record)), retry=progress.retry, reason=progress.reason,
        )


def _is_for(record: RunRecord, chapter_id: str) -> bool:
    return record.command == "simulation" and record.chapter == chapter_id


def _is_design_only(record: RunRecord) -> bool:
    return record.args.get("until") == "design"


def _stages(progress: Progress, is_design_only: bool = False) -> tuple[SimulationStage, ...]:
    shown = STAGES[:STAGES.index("design") + 1] if is_design_only else STAGES
    return tuple(SimulationStage(name=s, state=progress.stages[s]) for s in shown)


def _published(path: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8").strip().removeprefix(PREFIX).removesuffix(";")
        scenes = json.loads(text)["scenes"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return scenes if isinstance(scenes, dict) else {}
