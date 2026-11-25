"""Схемы данных из ТЗ: общий договор между этапами."""

import json
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent


@lru_cache
def load_schema(name: str) -> dict:
    return json.loads((FOLDER / f"{name}.schema.json").read_text(encoding="utf-8"))
