"""Публичный вход модуля: ролики. Другие модули импортируют только отсюда."""

from glava.modules.video.produce import Narration, produce
from glava.modules.video.spec import make_spec, spec_issues
from glava.modules.video.voices import (
    VoiceNotConfigured,
    list_voices,
    max_chars,
    voice_env,
    voice_from_env,
)

__all__ = [
    "Narration",
    "VoiceNotConfigured",
    "list_voices",
    "make_spec",
    "max_chars",
    "produce",
    "spec_issues",
    "voice_env",
    "voice_from_env",
]
