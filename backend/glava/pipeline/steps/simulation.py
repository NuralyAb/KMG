"""simulation: 3D-симулятор по узлу."""

import re
import shutil
import subprocess
from types import SimpleNamespace

from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.steps.course import build_site
from glava.shared.json_files import read, read_or
from glava.shared.paths import SIMULATORS


def build_simulation(chapter: Chapter, node_id: str, until: str | None) -> None:
    """3D-симулятор по узлу слоя. Конвейер сцен — на Node.js, потолки расхода — simulators/agent/steps.json."""
    if node_id not in {n["id"] for n in read(chapter.work / "layer.json")["nodes"]}:
        raise SystemExit(f"в слое нет узла {node_id}")
    program, folder = shutil.which("node"), SIMULATORS
    if program is None or not (folder / "node_modules").is_dir():
        raise SystemExit("нужен Node.js 22; один раз выполните: cd simulators; npm ci")
    job = re.sub(r"[^a-z0-9_]+", "_", node_id.lower())
    state = folder / "jobs" / job / "state.json"
    before = len(read_or(state, {}).get("spend", []))
    command = [program, "agent/pipeline.mjs", job, "--chapter", chapter.chapter_id, "--node", node_id, *(["--to", until] if until else [])]
    code = subprocess.run(command, cwd=folder, check=False).returncode  # noqa: S603 — аргументы проверены по слою
    spent = [SimpleNamespace(input_tokens=s.get("in") or 0, output_tokens=s.get("out") or 0, cost_usd=s.get("usd") or 0)
             for s in read_or(state, {}).get("spend", [])[before:]]
    if spent:
        write_metrics(chapter, "simulation", 1, spent)
    if code:
        raise SystemExit(code)
    if not until:
        build_site(chapter)
