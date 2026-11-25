"""Провайдеры моделей. Выбор: LLM_PROVIDER=claude_code|anthropic|openai|local, LLM_MODEL=<имя>."""

import base64
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

from glava.modules.llm.client import CACHE_BREAK, Provider, Reply
from glava.modules.llm.compatible import (
    LOCAL_URL,
    OPENAI_URL,
    OpenAiCompatible,
    is_loopback,
)
from glava.modules.llm.errors import ProviderUnavailable

RETRIES = 3
TIMEOUT_S = 900
DEFAULT_MODEL = "sonnet"
LONG_PROMPT_TOKENS = 100_000


@dataclass(frozen=True)
class Price:
    """Доллары за миллион токенов. Запись в кэш (5 минут) в 1,25 раза дороже входа."""

    tokens_in: float
    tokens_out: float
    cache_read: float

    def cost(self, fresh: int, written: int, read: int, out: int) -> float:
        return (fresh * self.tokens_in + written * self.tokens_in * 1.25 + read * self.cache_read + out * self.tokens_out) / 1_000_000


# цена нужна только провайдеру, который не сообщает стоимость сам; второе значение — для запросов длиннее LONG_PROMPT_TOKENS
PRICES: Mapping[str, tuple[Price, Price]] = {
    "claude-opus-5-5": (Price(4.0, 20.0, 0.2),) * 2,
    "claude-sonnet-5-5": (Price(2.0, 10.0, 0.1),) * 2,
    "claude-haiku-5-5": (Price(0.1, 0.5, 0.01), Price(0.5, 2.5, 0.05)),
}
KINDS = ("claude_code", "anthropic", "openai", "local")


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


def _text_blocks(prompt: str) -> list[dict]:
    """Общее начало запросов кэшируется у поставщика: повтор главы в каждом узле стоит двадцатую часть."""
    shared, mark, own = prompt.partition(CACHE_BREAK)
    if not mark:
        return [{"type": "text", "text": prompt}]
    return [{"type": "text", "text": shared, "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": own}]


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
            model=self.model, max_tokens=32_000, messages=[{"role": "user", "content": [*images, *_text_blocks(prompt)]}],
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        ) as stream:
            message = stream.get_final_message()
        usage = message.usage
        written, read = usage.cache_creation_input_tokens or 0, usage.cache_read_input_tokens or 0
        tokens_in = usage.input_tokens + written + read
        price = PRICES[self.model][tokens_in > LONG_PROMPT_TOKENS]
        text = "".join(b.text for b in message.content if b.type == "text")
        cost = price.cost(usage.input_tokens, written, read, usage.output_tokens)
        return Reply(text, self.model, tokens_in, usage.output_tokens, cost, is_cut=message.stop_reason == "max_tokens")


def _number(env: Mapping[str, str], name: str) -> float | None:
    raw = env.get(name)
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        value = -1.0
    if not (math.isfinite(value) and value >= 0):
        raise ProviderUnavailable(f"{name}: нужно неотрицательное число")
    return value


def _address(url: str) -> SplitResult:
    """Пароль или ключ внутри адреса попал бы в журнал и в имя кэша."""
    try:
        parts = urlsplit(url)
        is_plain = parts.scheme in ("http", "https") and parts.hostname and (parts.port or True)
    except ValueError:
        parts, is_plain = None, False
    if parts is None or not is_plain or "@" in parts.netloc or parts.query or parts.fragment or not url.isprintable():
        raise ProviderUnavailable("LLM_BASE_URL: нужен адрес вида http://127.0.0.1:11434/v1, без пароля, ключа и параметров")
    return parts


def _compatible(kind: str, env: Mapping[str, str]) -> Provider:
    """OpenAI или любой сервер с тем же API: Ollama, LM Studio, vLLM. Ключ OpenAI на чужой адрес не отправляется."""
    model = (env.get("LLM_MODEL") or "").strip()
    if not model:
        raise ProviderUnavailable(f"для LLM_PROVIDER={kind} укажите имя модели в LLM_MODEL")
    url = OPENAI_URL if kind == "openai" else (env.get("LLM_BASE_URL") or LOCAL_URL).rstrip("/")
    parts = _address(url)
    key = (env.get("OPENAI_API_KEY" if kind == "openai" else "LLM_API_KEY") or "").strip() or None
    # иначе ошибка заголовка напечатает ключ в журнал
    if key and not (key.isascii() and key.isprintable()):
        raise ProviderUnavailable("в ключе API недопустимые знаки: проверьте, что он скопирован целиком и без лишнего")
    if kind == "openai" and not key:
        raise ProviderUnavailable("для LLM_PROVIDER=openai нужен ключ в OPENAI_API_KEY")
    own_machine = is_loopback(url)
    if key and not own_machine and parts.scheme != "https":
        raise ProviderUnavailable("ключ не отправляется по http на другой компьютер: нужен адрес https")
    price_in, price_out = _number(env, "LLM_PRICE_IN"), _number(env, "LLM_PRICE_OUT")
    if kind == "openai" and not (price_in and price_out):
        raise ProviderUnavailable("для openai укажите цены LLM_PRICE_IN и LLM_PRICE_OUT больше нуля: иначе потолок расхода не сработает")
    if (price_in is None or price_out is None) and not (own_machine and price_in is price_out):
        raise ProviderUnavailable("цена модели неизвестна, бюджет не сработает: укажите LLM_PRICE_IN и LLM_PRICE_OUT "
                                  "(доллары за миллион токенов; 0, если бесплатно)")
    # одно имя модели на разных серверах — разные ответы, поэтому адрес входит в ключ кэша
    # имя попадает в слой и в git, поэтому сам адрес не пишется
    name = kind if kind == "openai" or url == LOCAL_URL else f"{kind}-{hashlib.sha256(url.encode()).hexdigest()[:8]}"
    context = _number(env, "LLM_CONTEXT")
    if kind == "local" and not context:
        raise ProviderUnavailable("укажите LLM_CONTEXT — размер контекста модели в токенах, как он настроен на сервере: иначе обрезка главы останется незамеченной")
    return OpenAiCompatible(model, url, key, price_in or 0.0, price_out or 0.0, name, int(context) if context else None)


def provider_from_env(env: Mapping[str, str] = os.environ) -> Provider:
    kind = env.get("LLM_PROVIDER", "claude_code")
    if kind in ("openai", "local"):
        return _compatible(kind, env)
    model = env.get("LLM_MODEL", DEFAULT_MODEL)
    if kind == "anthropic":
        if model not in PRICES:
            raise ProviderUnavailable(f"цена модели {model} неизвестна, бюджет не сработает: добавьте её в PRICES")
        return AnthropicApi(model)
    if kind != "claude_code":
        raise ProviderUnavailable(f"неизвестный LLM_PROVIDER: {kind}; есть {', '.join(KINDS)}")
    exe = env.get("CLAUDE_EXE") or env.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude")
    if not exe:
        raise ProviderUnavailable("Claude Code не найден: укажите путь в CLAUDE_EXE или выберите другой LLM_PROVIDER: anthropic, openai, local")
    return ClaudeCode(model, exe)
