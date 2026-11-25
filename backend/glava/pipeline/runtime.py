"""Модель и пределы: сколько запросов сразу и сколько можно потратить."""

import os
from collections.abc import Mapping

from glava.modules.llm.api import Provider, cached, metered, provider_from_env
from glava.shared.paths import MODEL_CACHE

PARALLEL = 4
BUDGET_USD = float(os.environ.get("GLAVA_BUDGET_USD", "25"))


def open_provider(env: Mapping[str, str] | None = None) -> Provider:
    return cached(metered(provider_from_env(os.environ if env is None else env), BUDGET_USD), MODEL_CACHE)


def verifier_env(env: Mapping[str, str]) -> dict[str, str]:
    """Проверяющая модель задаётся отдельно: LLM_VERIFY_MODEL, по умолчанию та же. Своя ошибка самому себе видна хуже."""
    model = env.get("LLM_VERIFY_MODEL")
    return {**env, "LLM_MODEL": model} if model else dict(env)
