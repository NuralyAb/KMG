"""Задания курса: пять типов, ключ проверяется кодом, ответ держится на утверждениях узла."""

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

import jsonschema

from glava.llm import Provider, Reply, ask_json
from glava.stages.layer import load_schema

MIN_TASKS = 15
MIN_TYPES = 4
GROUP = 4
GAP = re.compile(r"\{\{(\d+)\}\}")


def _key_issue(task: Mapping) -> str | None:
    kind, answer = task["type"], task["answer"]
    ids = [o["id"] for o in task.get("options") or []]
    if kind == "single" and answer not in ids:
        return "ответа нет среди вариантов"
    if kind == "multiple" and (not isinstance(answer, list) or len(answer) < 2 or not set(answer) <= set(ids) or len(answer) == len(ids)):
        return "нужны два и больше верных вариантов и хотя бы один неверный"
    if kind == "order" and (not isinstance(answer, list) or sorted(answer) != sorted(ids) or len(ids) < 2):
        return "порядок должен перечислять каждый вариант один раз"
    if kind == "gap" and (not isinstance(answer, list) or len(set(GAP.findall(task["prompt"]))) != len(answer) or not answer):
        return "число пропусков не совпадает с числом ответов"
    if kind == "calc" and (not isinstance(answer, int | float) or task.get("tolerance") is None or not task.get("unit")):
        return "для расчёта нужны число, tolerance и unit"
    return None


def task_issues(data: Mapping, nodes: Sequence[Mapping]) -> list[str]:
    validator = jsonschema.Draft202012Validator(load_schema("task"))
    problems = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:120]}" for e in validator.iter_errors({"chapter": "x", **data})]
    if problems:
        return problems
    claims = {n["id"]: {c["id"] for c in n["claims"]} for n in nodes}
    issues: list[str] = []
    for task in data["tasks"]:
        if task["step_id"] not in claims:
            issues.append(f"{task['id']}: узла {task['step_id']} нет")
        elif not set(task["claim_ids"]) <= claims[task["step_id"]]:
            issues.append(f"{task['id']}: claim_ids не из узла {task['step_id']}")
        problem = _key_issue(task)
        if problem:
            issues.append(f"{task['id']}: {problem}")
    return issues


def chapter_task_issues(tasks: Sequence[Mapping]) -> list[str]:
    types = {t["type"] for t in tasks}
    issues = [f"заданий {len(tasks)}, нужно {MIN_TASKS}"] if len(tasks) < MIN_TASKS else []
    return issues + ([f"типов заданий {len(types)}, нужно {MIN_TYPES}"] if len(types) < MIN_TYPES else [])


def number_tasks(tasks: Iterable[Mapping]) -> list[dict]:
    seen: Counter[str] = Counter()
    numbered = []
    for task in tasks:
        seen[task["step_id"]] += 1
        numbered.append({**task, "id": f"{task['step_id']}.t{seen[task['step_id']]}"})
    return numbered


def _brief(node: Mapping) -> dict:
    return {"id": node["id"], "title": node["title"], "layers": {k: v["text"] for k, v in node["layers"].items() if k != "deeper"},
            "claims": [{"id": c["id"], "text": c["text"]} for c in node["claims"]], "misconception": node.get("misconception"),
            "worked_examples": node.get("worked_examples", []), "decision_on_data": node.get("decision_on_data")}


def groups(nodes: Sequence[Mapping], size: int = GROUP) -> list[Sequence[Mapping]]:
    return [nodes[i:i + size] for i in range(0, len(nodes), size)]


def make_tasks(provider: Provider, system: str, group: Sequence[Mapping]) -> tuple[list[dict], list[Reply]]:
    prompt = "# Узлы\n" + json.dumps([_brief(n) for n in group], ensure_ascii=False, indent=0)
    data, replies = ask_json(provider, system, prompt, lambda d: task_issues(d, group))
    bad = {i.split(":")[0] for i in task_issues(data, group)}
    return [t for t in data["tasks"] if t["id"] not in bad], replies
