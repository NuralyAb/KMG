"""Какой моделью собирать. Выбор хранится в settings.local.json, ключи — только в переменных среды сервера."""

from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from glava_server.jsonstore import JsonStore
from glava_server.library import write_json
from glava_server.schemas import ModelChoice, ModelSettings

FILE = "settings.local.json"
NAMES = {"provider": "LLM_PROVIDER", "model": "LLM_MODEL", "base_url": "LLM_BASE_URL", "price_in": "LLM_PRICE_IN", "price_out": "LLM_PRICE_OUT",
         "budget_usd": "GLAVA_BUDGET_USD", "context": "LLM_CONTEXT"}
KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "local": "LLM_API_KEY"}


BROKEN = "settings.local.json повреждён"


def _plain(url: str | None) -> str | None:
    """Адрес с паролем или ключом внутри наружу не отдаётся."""
    try:
        return ModelChoice(provider="claude_code", base_url=url).base_url
    except ValidationError:
        return None


class ModelStore:
    def __init__(self, root: Path, env: Mapping[str, str], store: JsonStore | None = None) -> None:
        self._file = root / FILE
        self._env = env
        self._store = store or JsonStore()

    def _choice(self) -> ModelChoice | None:
        raw = self._store.read(self._file) if self._file.exists() else None
        if raw is None:
            return None
        try:
            return ModelChoice.model_validate(raw)
        except ValidationError:
            return None

    def env(self) -> dict[str, str]:
        """Окружение сборки. Сохранённый выбор заменяет переменные целиком: старый адрес не должен достаться новой модели."""
        choice = self._choice()
        if choice is None:
            # испорченный выбор не превращается молча в другую модель: сборка остановится с понятной ошибкой
            return {**self._env, "LLM_PROVIDER": BROKEN} if self._file.exists() else dict(self._env)
        kept = {k: v for k, v in self._env.items() if k not in {*NAMES.values(), "LLM_VERIFY_MODEL"} or k == "GLAVA_BUDGET_USD"}
        # ключ выдан для адреса из переменных среды и на другой адрес не отправляется
        if (choice.base_url or "").rstrip("/") != self._env.get("LLM_BASE_URL", "").rstrip("/"):
            kept.pop("LLM_API_KEY", None)
        chosen = {NAMES[k]: str(v) for k, v in choice.model_dump().items() if v is not None}
        return {**kept, **chosen}

    def view(self) -> ModelSettings:
        choice = self._choice()
        keys = {name: bool(self._env.get(variable)) for name, variable in KEYS.items()}
        if choice is not None:
            return ModelSettings(**choice.model_dump(), origin="file", keys=keys)
        provider = BROKEN if self._file.exists() else self._env.get("LLM_PROVIDER") or "claude_code"
        return ModelSettings(provider=provider, model=self._env.get("LLM_MODEL") or None, base_url=_plain(self._env.get("LLM_BASE_URL")), origin="env", keys=keys)

    def save(self, choice: ModelChoice) -> ModelSettings:
        write_json(self._file, choice.model_dump())
        return self.view()
