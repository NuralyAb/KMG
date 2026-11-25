"""Строки metrics.csv. Последняя строка может быть недописана."""

import csv
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from glava_server.schemas import MetricRow

log = logging.getLogger("glava_server")


@dataclass(frozen=True)
class Totals:
    cost_usd: float
    tokens_in: int
    tokens_out: int


def _number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(value)
    return number


def _row(raw: Mapping[str, str | None]) -> MetricRow | None:
    if any(raw.get(field) is None for field in MetricRow.model_fields):
        return None
    values = {k: str(raw[k]) for k in MetricRow.model_fields}
    try:
        return MetricRow(
            chapter=values["chapter"], stage=values["stage"], nodes=int(_number(values["nodes"])),
            llm_tokens_in=int(_number(values["llm_tokens_in"])), llm_tokens_out=int(_number(values["llm_tokens_out"])),
            money_usd=_number(values["money_usd"]), person_minutes=_number(values["person_minutes"]),
            mentor_minutes=_number(values["mentor_minutes"]), video_seconds=_number(values["video_seconds"]),
            manual_share=_number(values["manual_share"]),
        )
    except ValueError:
        return None


def read_metrics(path: Path) -> list[MetricRow]:
    try:
        with path.open(encoding="utf-8", newline="") as file:
            parsed = [_row(raw) for raw in csv.DictReader(file)]
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        log.warning("metrics.csv не прочитан: %s", error)
        return []
    good = [r for r in parsed if r is not None]
    if len(good) < len(parsed):
        log.warning("metrics.csv: пропущено строк %s", len(parsed) - len(good))
    return good


def totals(rows: Sequence[MetricRow]) -> Totals:
    return Totals(round(sum(r.money_usd for r in rows), 4), sum(r.llm_tokens_in for r in rows), sum(r.llm_tokens_out for r in rows))
