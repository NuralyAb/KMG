"""Расход: ответы."""

from glava.shared.http.dto import Model


class MetricRow(Model):
    chapter: str
    stage: str
    nodes: int
    llm_tokens_in: int
    llm_tokens_out: int
    money_usd: float
    person_minutes: float
    mentor_minutes: float
    video_seconds: float
    manual_share: float
