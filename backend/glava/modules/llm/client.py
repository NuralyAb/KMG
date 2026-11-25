"""Модель за узким интерфейсом: провайдер заменяется переменной среды, ответы кэшируются, расход считается."""

import hashlib
import json
import logging
import math
import os
import threading
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

from glava.modules.llm.errors import ProviderUnavailable

log = logging.getLogger(__name__)
# до этой метки запросы этапа одинаковы: поставщик, который умеет, кэширует начало
CACHE_BREAK = "\n\n<!-- дальше своё у каждого узла -->\n\n"


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class Reply:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    is_cut: bool = False  # модель упёрлась в длину: конец ответа потерян


class Provider(Protocol):
    name: str
    model: str

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply: ...


@dataclass(frozen=True)
class Ledger:
    """Расход по этапам; запись возвращает новый журнал."""

    budget_usd: float
    records: tuple[tuple[str, Reply], ...] = ()

    def add(self, stage: str, *replies: Reply) -> "Ledger":
        return replace(self, records=(*self.records, *((stage, r) for r in replies)))

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for _, r in self.records)

    def check(self) -> "Ledger":
        if self.cost_usd > self.budget_usd:
            raise BudgetExceeded(f"потрачено ${self.cost_usd:.2f} при бюджете ${self.budget_usd:.2f}")
        return self


def _saved_reply(path: Path) -> Reply | None:
    """Повреждённый файл кэша — промах, а не поломка прогона."""
    try:
        return Reply(**json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (ValueError, TypeError):
        log.warning("файл кэша повреждён, спрашиваю заново: %s", path.name)
        return None


@dataclass
class _Metered:
    """Общий счётчик расхода для всех потоков прогона."""

    inner: Provider
    budget_usd: float
    spent_usd: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply:
        with self.lock:
            if self.spent_usd >= self.budget_usd:
                raise BudgetExceeded(f"потрачено ${self.spent_usd:.2f} при бюджете ${self.budget_usd:.2f}")
        try:
            reply = self.inner.ask(system, prompt, *([files] if files else []))
        except ProviderUnavailable as error:
            self._spend(error.cost_usd)
            raise
        self._spend(reply.cost_usd)
        return reply

    def _spend(self, cost_usd: float) -> None:
        if not (math.isfinite(cost_usd) and cost_usd >= 0):
            raise BudgetExceeded("стоимость ответа неизвестна: потолок расхода не работает")
        with self.lock:
            self.spent_usd += cost_usd


def metered(provider: Provider, budget_usd: float) -> Provider:
    return _Metered(provider, budget_usd)


@dataclass(frozen=True)
class _Cached:
    inner: Provider
    folder: Path

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    def _path(self, system: str, prompt: str, files: Sequence[Path]) -> Path:
        marks = [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
        key = hashlib.sha256("\0".join([self.name, self.model, system, prompt, *marks]).encode()).hexdigest()[:32]
        return self.folder / f"{key}.json"

    def forget(self, system: str, prompt: str, files: Sequence[Path] = ()) -> None:
        """Неудачный ответ не должен возвращаться при повторе команды."""
        self._path(system, prompt, files).unlink(missing_ok=True)

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply:
        path = self._path(system, prompt, files)
        saved = _saved_reply(path)
        if saved:
            return replace(saved, cost_usd=0.0)
        reply = self.inner.ask(system, prompt, *([files] if files else []))
        if reply.is_cut:
            return reply
        self.folder.mkdir(parents=True, exist_ok=True)
        draft = path.with_suffix(f".{threading.get_ident()}.tmp")
        draft.write_text(json.dumps(asdict(reply), ensure_ascii=False), encoding="utf-8")
        os.replace(draft, path)
        return reply


def cached(provider: Provider, folder: Path) -> Provider:
    return _Cached(provider, folder)


def extract_json(text: str) -> Any:
    """Первый целый JSON-объект или массив в ответе модели."""
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char in "{[":
            try:
                return decoder.raw_decode(text, start)[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("в ответе нет целого JSON")


def ask_json(
    provider: Provider, system: str, prompt: str, validate: Callable[[Any], list[str]], attempts: int = 3,
    files: Sequence[Path] = (),
) -> tuple[Any, list[Reply]]:
    """Ответ в JSON; замечания проверки возвращаются модели. После последней попытки отдаётся последний разобранный ответ."""
    asked: list[str] = []
    is_good = False
    try:
        data, replies, is_good = _ask_until_good(provider, system, prompt, validate, attempts, files, asked)
        return data, replies
    finally:
        # и после сбоя посреди попыток: неудачный ответ не должен вернуться из кэша
        if not is_good and hasattr(provider, "forget"):
            for failed in asked:
                provider.forget(system, failed, files)


def _ask_until_good(
    provider: Provider, system: str, prompt: str, validate: Callable[[Any], list[str]], attempts: int, files: Sequence[Path], asked: list[str],
) -> tuple[Any, list[Reply], bool]:
    replies: list[Reply] = []
    data: Any = None
    issues: list[str] = []
    question = prompt
    for attempt in range(attempts):
        asked.append(question)
        reply = provider.ask(system, question, *([files] if files else []))
        replies.append(reply)
        try:
            if reply.is_cut:
                raise ValueError("ответ обрезан по длине, пиши короче")
            data = extract_json(reply.text)
            issues = validate(data)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError, ArithmeticError, RecursionError) as error:
            issues = [f"ответ не разобран как JSON нужной формы: {error!r}"]
        if not issues:
            return data, replies, True
        log.info("попытка %s: замечаний %s", attempt + 1, len(issues))
        question = (f"{prompt}\n\n# Твой прошлый ответ\n{reply.text}\n\n# Замечания машинной проверки\n"
                    + "\n".join(f"- {i}" for i in issues[:40]) + "\n\nИсправь только это и верни полный JSON заново.")
    if data is None:
        raise ValueError("модель не вернула JSON: " + "; ".join(issues[:3]))
    return data, replies, False
