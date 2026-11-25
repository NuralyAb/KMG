"""Состояние: ответы."""

from typing import Literal

from glava.shared.http.dto import Model


class Health(Model):
    status: Literal["ok"] = "ok"
    provider: str
    model: str
    claude_found: bool
    ffmpeg_found: bool
