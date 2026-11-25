"""Промпты этапов."""

from pathlib import Path

FOLDER = Path(__file__).parent / "prompts"


def prompt_file(name: str, english: bool = False) -> str:
    """Для английской главы к промпту дописывается добавка. Запрос по русской главе не меняется ни на байт: от него зависит ключ оплаченного кэша."""
    base, extra = (FOLDER / f"{name}.md").read_text(encoding="utf-8"), FOLDER / "english" / f"{name}.md"
    return f"{base}\n{extra.read_text(encoding='utf-8')}" if english and extra.exists() else base
