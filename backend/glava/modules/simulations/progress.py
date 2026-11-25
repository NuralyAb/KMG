"""Ход работы агента над симулятором: по журналу запуска видно, какой этап готов и какой идёт."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

StageState = Literal["wait", "now", "done", "failed"]

# порядок конвейера simulators/agent/pipeline.mjs; course — сборка курса после него
STAGES = ("facts", "design", "model", "scene", "game", "look", "finish", "course")
TOGETHER = frozenset({"scene", "game"})  # строятся одновременно
MARK = re.compile(r"([>✓=]) (\w+)(?:\b.*?\(исправление (\d+)\))?")
ENDED = ("привязано к шагу", "✓ Готово")
COURSE = "курс: "
REASON = 300


@dataclass(frozen=True)
class Progress:
    stages: dict[str, StageState]
    retry: int
    reason: str | None


def read_progress(lines: Iterable[str], is_running: bool) -> Progress:
    stages: dict[str, StageState] = dict.fromkeys(STAGES, "wait")
    retry, reason = 0, None
    for line in lines:
        if line.startswith(("✗ ", "■ ")):
            reason = line[2:].strip()[:REASON]
        elif line.startswith(ENDED):
            stages |= dict.fromkeys(STAGES[:-1], "done")
        elif line.startswith(COURSE):
            stages |= dict.fromkeys(STAGES, "done")
        elif (found := MARK.match(line)) and found[2] in stages:
            sign, name = found[1], found[2]
            stages[name] = "now" if sign == ">" else "done"
            retry = int(found[3] or 0) if sign == ">" else 0
            # начатый этап значит, что прежние готовы, даже если они строчки не оставили
            stages |= {s: "done" for s in STAGES[:STAGES.index(name)] if not {s, name} <= TOGETHER}
    current = [s for s in STAGES if stages[s] == "now"]
    if is_running and not current:
        stages |= {s: "now" for s in [s for s in STAGES if stages[s] == "wait"][:1]}
    if not is_running:
        stages |= dict.fromkeys(current, "failed")
    return Progress(stages, retry, reason)
