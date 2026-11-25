"""Публичный вход модуля: озвученные разборы шагов. Другие модули импортируют только отсюда."""

from glava.modules.narration.build import narrate, ready_narrations
from glava.modules.narration.script import reader
from glava.modules.narration.voice import Voice, VoiceFailed

__all__ = [
    "Voice",
    "VoiceFailed",
    "narrate",
    "reader",
    "ready_narrations",
]
