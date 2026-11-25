"""Промпты этапов."""

from pathlib import Path

FOLDER = Path(__file__).parent / "prompts"


def prompt_file(name: str) -> str:
    return (FOLDER / f"{name}.md").read_text(encoding="utf-8")
