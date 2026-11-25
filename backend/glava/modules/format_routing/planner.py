"""Маршрутизация: формат подачи для каждого узла с оценкой видеоёмкости."""

import json
from collections import Counter
from collections.abc import Mapping, Sequence

import jsonschema

from glava.modules.llm.api import Provider, Reply, ask_json
from glava.shared.json_schemas import load_schema

HOOK_SHARE_LIMIT = 0.2


def _schema_issues(data: Mapping) -> list[str]:
    validator = jsonschema.Draft202012Validator(load_schema("routing"))
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:120]}" for e in validator.iter_errors({"chapter": "x", **data})]


def routing_issues(data: Mapping, nodes: Sequence[Mapping]) -> list[str]:
    problems = _schema_issues(data)
    if problems:
        return problems
    counts = Counter(r["node_id"] for r in data["routes"])
    known = {n["id"] for n in nodes}
    issues = [f"для узла {n} записей {counts[n]}, нужна одна" for n in known if counts[n] != 1]
    issues += [f"узла {n} нет в слое" for n in counts if n not in known]
    videos = [r for r in data["routes"] if r["format"] in ("шортс", "длинное видео")]
    hooks = [r for r in videos if r.get("hook_short")]
    if videos and len(hooks) / len(videos) > HOOK_SHARE_LIMIT:
        issues.append("шортсов-крючков больше 20% роликов")
    return issues


def make_routing(provider: Provider, system: str, layer: Mapping, templates: str) -> tuple[dict, list[Reply]]:
    nodes = layer["nodes"]
    listed = [{"node_id": n["id"], "title": n["title"], "difficulty": n["difficulty"], "main": n["layers"]["main"]["text"],
               "decision_on_data": bool(n.get("decision_on_data"))} for n in nodes]
    prompt = f"# Шаблоны сцен\n{templates}\n\n# Узлы\n{json.dumps(listed, ensure_ascii=False, indent=0)}"
    data, replies = ask_json(provider, system, prompt, lambda d: routing_issues(d, nodes))
    return {"chapter": layer["chapter"], "routes": data["routes"]}, replies
