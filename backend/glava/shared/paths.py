"""Где что лежит. Других мест, знающих раскладку репозитория, быть не должно."""

import os
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SIMULATORS = REPOSITORY / "simulators"
# ответы модели оплачены: кэш не зависит от рабочей папки
MODEL_CACHE = REPOSITORY / ".cache"
# данные конвейера: реестр глав, доменные пакеты, слои, курсы, загрузки
WORKSPACE = Path(os.environ["GLAVA_ROOT"]).resolve() if os.environ.get("GLAVA_ROOT") else REPOSITORY / "workspace"


def workspace() -> Path:
    return WORKSPACE
