"""Запись расхода этапа в metrics.csv."""

import csv
from collections.abc import Sequence
from typing import Protocol

from glava.shared.paths import workspace

METRIC_FIELDS = ("chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes", "mentor_minutes",
                 "video_seconds", "manual_share")


class Spent(Protocol):
    """Ответ модели или строка расхода внешнего конвейера."""

    input_tokens: int
    output_tokens: int
    cost_usd: float


def append_metrics(chapter_id: str, stage: str, nodes: int, replies: Sequence[Spent], video_seconds: float = 0) -> None:
    path = workspace() / "metrics.csv"
    is_new = not path.exists()
    row = [chapter_id, stage, nodes, sum(r.input_tokens for r in replies), sum(r.output_tokens for r in replies),
           f"{sum(r.cost_usd for r in replies):.4f}", 0, 0, video_seconds, 0]
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        if is_new:
            writer.writerow(METRIC_FIELDS)
        writer.writerow(row)
