"""Спецификация ролика от модели: сценарий, действия сцены, честность, чек-лист; код не пускает её дальше с замечаниями."""

import json
from collections.abc import Mapping, Sequence
from types import ModuleType
from typing import Any

import jsonschema

from glava.modules.llm.api import Provider, Reply, ask_json
from glava.modules.video.check import motion_errors, script_errors

TEXT = {"type": "string", "minLength": 2}
TEXTS = {"type": "array", "minItems": 1, "items": TEXT}
BEAT = {
    "type": "object", "required": ["say", "claim_id", "on_screen", "label", "frame_class", "action", "is_analogy", "pause_after", "role"],
    "properties": {
        "say": TEXT, "claim_id": {"type": ["string", "null"]}, "on_screen": TEXT, "label": {"enum": ["реальные данные", "симуляция", "схема"]},
        "frame_class": {"enum": ["A", "B", "C", "D"]}, "action": {"type": "object", "additionalProperties": {"type": "number"}}, "is_analogy": {"type": "boolean"},
        "pause_after": {"type": "number", "minimum": 0, "maximum": 1.5}, "role": {"enum": ["hook", "step", "prediction", "answer", "limits", "decision", "frame", "transfer"]},
    },
}
SCHEMA = {
    "type": "object",
    "required": ["title", "params", "objects", "invariants", "assumptions", "exaggerations", "plaque", "prediction_question", "transfer_question", "data_it_bridge",
                 "terms_to_check", "physics", "beats"],
    "properties": {
        "title": {"type": ["string", "null"]}, "params": {"type": "object"}, "objects": TEXTS, "invariants": TEXTS, "assumptions": TEXTS, "exaggerations": TEXTS,
        "plaque": TEXTS, "prediction_question": TEXT, "transfer_question": TEXT, "data_it_bridge": TEXT, "terms_to_check": {"type": "array", "items": TEXT},
        "physics": {"type": "object", "additionalProperties": {"type": "object", "required": ["answer", "note"], "properties": {"answer": {"enum": ["да", "нет", "н/п"]}}}},
        "beats": {"type": "array", "minItems": 4, "items": BEAT},
    },
}
WORDS = {"short": (85, 150), "wide": (190, 340)}


def spec_issues(spec: Any, node: Mapping[str, Any], template: ModuleType, checklist: Sequence[Mapping[str, str]], kind: str) -> list[str]:
    full = {"title": None, **spec} if isinstance(spec, Mapping) else spec
    problems = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:140]}" for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(full)]
    if problems:
        return problems
    issues = [*script_errors(full, node), *template.check(full["params"], full["beats"])]
    if not issues and hasattr(template, "initial"):
        issues = motion_errors(full["beats"], template.initial(full["params"]))
    low, high = WORDS[kind]
    words = sum(len(b["say"].split()) for b in full["beats"])
    if not low <= words <= high:
        issues.append(f"слов в закадре {words}, нужно {low}–{high}")
    for item in checklist:
        answer = full["physics"].get(item["id"])
        if answer is None or answer["answer"] == "нет" or not str(answer["note"]).strip():
            issues.append(f"чек-лист {item['id']}: нужен ответ «да» или «н/п» с пояснением, иначе исправь сцену")
    return issues


def make_spec(
    provider: Provider, system: str, node: Mapping[str, Any], template: ModuleType, template_name: str, checklist: Sequence[Mapping[str, str]], kind: str,
    video_id: str, chapter: str,
) -> tuple[dict[str, Any], list[Reply]]:
    shown = {k: node.get(k) for k in ("id", "title", "short_title", "layers", "claims", "misconception", "data_meaning", "it_analogy", "now_practice", "decision_on_data")}
    low, high = WORDS[kind]
    prompt = (f"# Формат\n{'шортс 9:16' if kind == 'short' else 'разбор 16:9'}, слов в закадре {low}–{high}\n\n# Шаблон сцены\n{template.SUMMARY}\n\n"
              f"# Чек-лист\n{json.dumps(list(checklist), ensure_ascii=False)}\n\n# Узел\n{json.dumps(shown, ensure_ascii=False, indent=0)}")
    data, replies = ask_json(provider, system, prompt, lambda d: spec_issues(d, node, template, checklist, kind), attempts=5)
    left = spec_issues(data, node, template, checklist, kind)
    if left:
        raise ValueError("спецификация ролика не прошла проверку: " + "; ".join(left[:6]))
    return {**data, "video_id": video_id, "chapter": chapter, "node_id": node["id"], "format": kind, "template": template_name}, replies
