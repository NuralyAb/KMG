"""Провайдеры моделей. Выбор: LLM_PROVIDER=claude_code|anthropic, LLM_MODEL=<имя>."""

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from glava.llm import Provider, Reply

RETRIES = 3
TIMEOUT_S = 900
DEFAULT_MODEL = "sonnet"
# цена за миллион токенов (вход, выход) нужна только провайдеру, который не сообщает стоимость сам
PRICES: Mapping[str, tuple[float, float]] = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (1.0, 5.0)}


class ProviderUnavailable(RuntimeError):
    pass


def _payload(stdout: str) -> dict | None:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class ClaudeCode:
    """Установленный Claude Code в режиме без инструментов и без настроек пользователя."""

    model: str
    exe: str
    name: str = "claude_code"

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply:
        # картинки копируются в чистую папку; чтение вне её в этом режиме не разрешается
        command = [self.exe, "-p", "--output-format", "json", "--model", self.model, "--tools", "Read" if files else "", "--strict-mcp-config",
                   "--setting-sources", "", "--system-prompt", system]
        detail = ""
        for attempt in range(RETRIES):
            with tempfile.TemporaryDirectory() as clean_folder:
                copies = [shutil.copy2(file, clean_folder) for file in files]
                question = f"Сначала открой инструментом Read картинки: {', '.join(copies)}. {prompt}" if files else prompt
                try:
                    done = subprocess.run(command, input=question, capture_output=True, text=True, encoding="utf-8",
                                          cwd=clean_folder, timeout=TIMEOUT_S, check=False)
                except subprocess.TimeoutExpired:
                    detail = f"нет ответа за {TIMEOUT_S} с"
                    continue
            payload = _payload(done.stdout)
            if payload is not None and not payload.get("is_error"):
                usage = payload["usage"]
                tokens_in = usage["input_tokens"] + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                return Reply(payload["result"], self.model, tokens_in, usage["output_tokens"], payload.get("total_cost_usd", 0.0))
            detail = str((payload or {}).get("result") or done.stderr or done.stdout)
            if attempt < RETRIES - 1:
                time.sleep(5 * 2**attempt)
        raise ProviderUnavailable(f"Claude Code не ответил: {detail[:400]}")


@dataclass(frozen=True)
class AnthropicApi:
    """Ключ берётся из ANTHROPIC_API_KEY; пакет anthropic ставится отдельно."""

    model: str
    name: str = "anthropic"

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply:
        import anthropic

        images = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(f.read_bytes()).decode()}}
                  for f in files]

        client = anthropic.Anthropic(max_retries=RETRIES)
        with client.messages.stream(
            model=self.model, max_tokens=32_000, messages=[{"role": "user", "content": [*images, {"type": "text", "text": prompt}]}],
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        ) as stream:
            message = stream.get_final_message()
        price_in, price_out = PRICES.get(self.model, (0.0, 0.0))
        usage = message.usage
        cost = (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000
        text = "".join(b.text for b in message.content if b.type == "text")
        return Reply(text, self.model, usage.input_tokens, usage.output_tokens, cost)


def provider_from_env(env: Mapping[str, str] = os.environ) -> Provider:
    kind = env.get("LLM_PROVIDER", "claude_code")
    model = env.get("LLM_MODEL", DEFAULT_MODEL)
    if kind == "anthropic":
        return AnthropicApi(model)
    if kind != "claude_code":
        raise ProviderUnavailable(f"неизвестный LLM_PROVIDER: {kind}")
    exe = env.get("CLAUDE_EXE") or env.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude")
    if not exe:
        raise ProviderUnavailable("Claude Code не найден: укажите путь в CLAUDE_EXE или выберите LLM_PROVIDER=anthropic")
    return ClaudeCode(model, exe)
