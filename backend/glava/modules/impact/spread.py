"""Разносит исправленное число по связному тексту узла и заданиям. Без модели и только там, где это однозначно."""

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from glava.modules.impact.diff import Change
from glava.shared.evidence import SERVICE_KEYS, node_texts, numbers_in

WORD = re.compile(r"[а-яёa-z]{4,}", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?;])\s+")
STEM = 6
MIN_COMMON = 2
# слова автора не правятся: разобранные примеры, задачи книги, таблицы и формулы
AUTHOR_FIELDS = frozenset({
    "claims", "worked_examples", "book_tasks", "tables", "formulas", "unit_ids", "pages", "links", "needs_scan", "terms_used", "terms_introduced", "id", "order"})


def stems(text: str) -> set[str]:
    return {w.casefold()[:STEM] for w in WORD.findall(text)}


def number_pattern(number: str) -> re.Pattern[str]:
    whole, _, part = number.partition(".")
    return re.compile(rf"(?<![\d.,]){re.escape(whole)}" + (rf"[.,]{re.escape(part)}0*" if part else "") + r"(?!\d|[.,]\d)")


def single_swap(change: Change) -> tuple[str, str] | None:
    """Одно число заменено ровно одним другим — тогда понятно, что на что менять."""
    if change.kind == "changed" and len(change.old_numbers) == len(change.new_numbers) == 1:
        return change.old_numbers[0], change.new_numbers[0]
    return None


def _label(text: str, number: str) -> str | None:
    """Обозначение слева от числа: «Pн.кр» из «Pн.кр = 3»."""
    found = re.search(rf"([^\s=<>≈,;]+)\s*[=<>≈]\s*{number_pattern(number).pattern}", text)
    return found.group(1) if found else None


def _is_about(piece: str, change: Change, old: str) -> bool:
    """Фраза о том же: общие слова, то же обозначение перед числом или другие числа утверждения рядом."""
    if len(stems(piece) & stems(change.before)) >= MIN_COMMON:
        return True
    label = _label(change.before, old)
    if label is not None and label == _label(piece, old):
        return True
    return len((numbers_in(piece) & numbers_in(change.before)) - {old}) >= MIN_COMMON


def leftovers(node: Mapping[str, Any], change: Change) -> list[dict[str, str]]:
    """Где в узле ещё стоит старое число: код не уверен, что оно о том же, или это слова автора."""
    old = [number_pattern(n) for n in change.old_numbers]
    return [{"where": f"{node['id']}.{where}", "text": text} for where, text in node_texts(node)
            if where != change.claim_id and "#" not in where and any(p.search(text) for p in old)]


def patch_number(text: str, change: Change, loose: bool = False) -> str:
    """Меняет число только в тех фразах, что говорят о том же."""
    swap = single_swap(change)
    if swap is None:
        return text
    old, new = number_pattern(swap[0]), swap[1].replace(".", ",")
    out, at = [], 0
    for gap in [*SENTENCE.finditer(text), None]:
        piece = text[at:gap.start() if gap else len(text)]
        out.append(old.sub(new, piece) if loose or _is_about(piece, change, swap[0]) else piece)
        if gap:
            out.append(gap.group())
            at = gap.end()
    return "".join(out)


def _walk(value: Any, where: str, change: Change, log: list[dict[str, str]]) -> Any:
    if isinstance(value, str):
        fixed = patch_number(value, change)
        if fixed != value:
            log.append({"where": where, "before": value, "after": fixed})
        return fixed
    if isinstance(value, Mapping):
        return {k: v if k in SERVICE_KEYS else _walk(v, f"{where}.{k}", change, log) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, f"{where}[{i}]", change, log) for i, v in enumerate(value)]
    return value


def _spread_node(node: Mapping[str, Any], change: Change, log: list[dict[str, str]]) -> dict[str, Any]:
    fresh = {k: v if k in AUTHOR_FIELDS or k == "numbers" else _walk(v, f"{node['id']}.{k}", change, log) for k, v in node.items()}
    rows = []
    for i, row in enumerate(node.get("numbers") or []):
        # строка «Цифры и условия» привязана к утверждению: общих слов искать не нужно
        text = patch_number(row["text"], change, loose=True) if row.get("claim_id") == change.claim_id else row["text"]
        if text != row["text"]:
            log.append({"where": f"{node['id']}.numbers[{i}]", "before": row["text"], "after": text})
        rows.append({**row, "text": text})
    return {**fresh, "numbers": rows} if "numbers" in node else fresh


def task_text(task: Mapping[str, Any]) -> str:
    answers = task["answer"] if isinstance(task["answer"], list) else [task["answer"]]
    return " ".join([task["prompt"], task.get("explanation") or "", *(o["text"] for o in task.get("options") or []), *(str(a).replace(".", ",") for a in answers)])


def _spread_task(task: Mapping[str, Any], change: Change, log: list[dict[str, str]]) -> dict[str, Any] | None:
    """None — задание само не исправить: ответ считается из числа, чисел несколько или варианты совпали."""
    text = task_text(task)
    if not any(number_pattern(n).search(text) for n in change.old_numbers):
        return dict(task)
    swap = single_swap(change)
    if swap is None or task["type"] == "calc":
        return None
    old, new = number_pattern(swap[0]), swap[1].replace(".", ",")
    fresh = deepcopy(dict(task))
    fresh["prompt"] = old.sub(new, task["prompt"])
    fresh["explanation"] = old.sub(new, task.get("explanation") or "")
    for option in fresh.get("options") or []:
        option["text"] = old.sub(new, option["text"])
    if task["type"] == "gap":
        fresh["answer"] = [old.sub(new, str(a)) for a in task["answer"]]
    texts = [o["text"] for o in fresh.get("options") or []]
    if len(set(texts)) < len(texts):
        return None
    log.append({"where": task["id"], "before": text, "after": task_text(fresh)})
    return fresh


def spread(layer: Mapping[str, Any], tasks: Sequence[Mapping[str, Any]], found: Sequence[Change]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]], list[str]]:
    """Новый слой, новые задания, журнал замен и задания, которые нужно составить заново."""
    log: list[dict[str, str]] = []
    nodes = list(layer["nodes"])
    ready: list[Mapping[str, Any]] = list(tasks)
    broken: set[str] = set()
    for change in found:
        if single_swap(change) is not None:
            nodes = [_spread_node(n, change, log) if n["id"] == change.node_id else n for n in nodes]
        for i, task in enumerate(ready):
            if change.claim_id not in (task.get("claim_ids") or []):
                continue
            fresh = None if change.kind == "removed" else _spread_task(task, change, log)
            if fresh is None:
                broken.add(task["id"])
            else:
                ready[i] = fresh
    return {**layer, "nodes": nodes}, [dict(t) for t in ready], log, sorted(broken)
