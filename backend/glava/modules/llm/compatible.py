"""Модель за OpenAI-совместимым API: OpenAI, Ollama, LM Studio, vLLM. Только стандартная библиотека."""

import base64
import ipaddress
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from glava.modules.llm.client import Reply
from glava.modules.llm.errors import ProviderUnavailable

OPENAI_URL = "https://api.openai.com/v1"
LOCAL_URL = "http://127.0.0.1:11434/v1"
RETRIES = 3
TIMEOUT_S = 900
RETRY_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})
# плотнее текст на токены не ложится: значит, сервер отбросил часть главы
MAX_CHARS_RU, MAX_CHARS_OTHER, MAX_CHARS_FULL_WINDOW = 4.2, 6.0, 3.0
MIN_FULL_WINDOW = 2048
MIN_SECRET = 16
CUT_REASONS = frozenset({"length", "max_tokens", "content_filter"})
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
END_OF_THOUGHTS = "</think>"


def without_thoughts(text: str) -> str:
    """Рассуждения модели до ответа; тег внутри самого ответа не в счёт."""
    _, mark, after = text.rpartition(END_OF_THOUGHTS)
    if mark and re.search(r"[{\[]", after):
        return after
    return "" if text.lstrip().startswith("<think>") and not mark else text
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Перенаправление унесло бы ключ и текст главы на другой адрес."""

    def redirect_request(self, *_: Any) -> None:
        return None


def is_loopback(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _image(file: Path) -> dict[str, Any]:
    data = base64.b64encode(file.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{IMAGE_TYPES.get(file.suffix.lower(), 'image/png')};base64,{data}"}}


def _error_text(error: urllib.error.HTTPError) -> str:
    try:
        raw = error.read().decode("utf-8", "replace")
    except (OSError, HTTPException):
        return "текст ошибки не прочитан"
    try:
        found = json.loads(raw)["error"]
        return str(found["message"] if isinstance(found, dict) else found)
    except (ValueError, KeyError, TypeError, RecursionError):
        return raw


def _tokens(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


@dataclass(frozen=True)
class OpenAiCompatible:
    model: str
    base_url: str
    key: str | None = field(repr=False, default=None)
    price_in: float = 0.0
    price_out: float = 0.0
    name: str = "local"
    context: int | None = None

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply:
        content: Any = [*map(_image, files), {"type": "text", "text": prompt}] if files else prompt
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        return self._reply(self._post(json.dumps(body).encode()), system + prompt)

    def _shown(self, text: str) -> str:
        """Сервер может вернуть ключ в тексте ошибки или ответа: дальше он не уходит."""
        return text.replace(self.key, "[ключ]") if self.key else text

    def _refuse(self, why: str, cost_usd: float = 0.0) -> ProviderUnavailable:
        return ProviderUnavailable(self._shown(f"модель {self.model} ({self.name}): {why}")[:500], cost_usd)

    def _post(self, body: bytes) -> Any:
        headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {self.key}"} if self.key else {})}
        # системный прокси не должен видеть запрос к своему же компьютеру
        direct = [urllib.request.ProxyHandler({})] if is_loopback(self.base_url) else []
        opener = urllib.request.build_opener(_NoRedirect, *direct)
        detail = ""
        for attempt in range(RETRIES):
            request = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST")
            try:
                with opener.open(request, timeout=TIMEOUT_S) as answer:
                    raw = answer.read()
            except urllib.error.HTTPError as error:
                detail = f"код {error.code}: {_error_text(error)}"
                if error.code not in RETRY_CODES:
                    break
            except (OSError, HTTPException) as error:
                detail = f"{type(error).__name__}: {error}"
            else:
                try:
                    return json.loads(raw)
                except (ValueError, RecursionError):
                    # ответ уже оплачен: повтор заплатил бы ещё раз за то же самое
                    raise self._refuse("ответ сервера не JSON") from None
            if attempt < RETRIES - 1:
                time.sleep(5 * 2**attempt)
        raise self._refuse(f"нет ответа: {detail}")

    def _reply(self, data: Any, asked: str) -> Reply:
        try:
            choice, usage = data["choices"][0], data.get("usage")
            text, reason = choice["message"].get("content") or "", choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise self._refuse("ответ не в формате OpenAI") from None
        usage = usage if isinstance(usage, dict) else {}
        tokens_in, tokens_out = _tokens(usage.get("prompt_tokens")), _tokens(usage.get("completion_tokens"))
        if not isinstance(text, str):
            raise self._refuse("ответ не в формате OpenAI")
        if not tokens_in or tokens_out is None:
            raise self._refuse("сервер не сообщает число токенов: нельзя проверить ни обрезку запроса, ни расход")
        cost = (tokens_in * self.price_in + tokens_out * self.price_out) / 1_000_000
        if self._is_prompt_cut(tokens_in, tokens_out, asked):
            # ответ по обрывку главы выглядит правдоподобно, поэтому он не принимается и не попадает в кэш
            raise self._refuse(f"сервер учёл {tokens_in} токенов на {len(asked)} знаков запроса: часть главы отброшена. Увеличьте контекст модели "
                               "(для Ollama — OLLAMA_CONTEXT_LENGTH)", cost)
        clean = without_thoughts(text)
        # короткий ключ-заглушка вроде «ollama» встречается в обычном тексте: вырезать его — исказить ответ
        clean = self._shown(clean) if self.key and len(self.key) >= MIN_SECRET else clean
        return Reply(clean, self.model, tokens_in, tokens_out, cost, is_cut=reason in CUT_REASONS)

    def _is_prompt_cut(self, tokens_in: int, tokens_out: int, asked: str) -> bool:
        """Обрезанный запрос занимает окно целиком: число токенов равно его размеру, а он бывает степенью двойки."""
        if self.context is not None and tokens_in + tokens_out >= self.context:
            return True
        density = len(asked) / tokens_in
        is_full_window = tokens_in >= MIN_FULL_WINDOW and tokens_in & (tokens_in - 1) == 0
        limit = MAX_CHARS_RU if len(CYRILLIC.findall(asked)) * 2 > len(asked) else MAX_CHARS_OTHER
        return density > limit or (is_full_window and density > MAX_CHARS_FULL_WINDOW)
