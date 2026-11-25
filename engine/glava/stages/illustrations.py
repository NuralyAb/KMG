"""Иллюстрации шагов: модель выбирает шаблон и заполняет спецификацию, код проверяет её и рисует SVG."""

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from glava.llm import Provider, Reply, ask_json
from glava.scenes import render, scene_issues
from glava.verify import unsupported_numbers

FIELDS = ("node_id", "template", "caption", "alt", "claim_ids", "data")
MAX_CAPTION = 200
Templates = Mapping[str, ModuleType]


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, inner in value.items():
            if key not in ("formula", "id"):
                yield from _strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _strings(inner)


def _values(scene: Mapping[str, Any]) -> list[float]:
    """Числа, которые читатель увидит как числа главы."""
    data = scene["data"]
    if scene["template"] == "bars":
        return [i[k] for i in data["items"] for k in ("value", "from", "to") if k in i]
    if scene["template"] == "plot" and data.get("numeric"):
        points = [v for s in data["series"] for p in s.get("points", []) for v in p]
        return points + list(data.get("params", {}).values())
    return []


def _source(node: Mapping[str, Any], claim_ids: Sequence[str]) -> str:
    claims = [c for c in node["claims"] if c["id"] in claim_ids]
    examples = [json.dumps(e, ensure_ascii=False) for e in node.get("worked_examples") or []]
    return "\n".join([*(c["text"] for c in claims), *(c["quote"] for c in claims), *examples])


def _scene_problems(scene: Mapping[str, Any], node: Mapping[str, Any], templates: Templates, style: Mapping[str, Any]) -> list[str]:
    template = templates.get(scene["template"])
    if template is None:
        return [f"шаблона {scene['template']} нет"]
    known = {c["id"] for c in node["claims"]}
    if not scene["claim_ids"] or not set(scene["claim_ids"]) <= known:
        return ["claim_ids должны быть непустыми и из этого узла"]
    problems = [f"{scene['template']}: {i}" for i in scene_issues(template, scene["data"], style)]
    if problems:
        return problems
    shown = " ; ".join([scene["caption"], scene["alt"], *_strings(scene["data"]), *(f"{v:g}" for v in _values(scene))])
    raw = [t for t in (scene["caption"], scene["alt"], *_strings(scene["data"])) if set(t) & set("_$\\")]
    if raw and scene["template"] != "plot" or any(set(t) & set("_$\\") for t in (scene["caption"], scene["alt"])):
        problems = [f"подписи без подчёркиваний и LaTeX: {raw[0][:40]}"]
    foreign = unsupported_numbers(shown, _source(node, scene["claim_ids"]))
    if foreign:
        problems = [*problems, f"чисел нет в утверждениях claim_ids: {', '.join(sorted(foreign))}"]
    return problems + ([f"подпись длиннее {MAX_CAPTION} знаков"] if len(scene["caption"]) > MAX_CAPTION else [])


def illustration_issues(data: Mapping[str, Any], nodes: Sequence[Mapping], templates: Templates, style: Mapping[str, Any]) -> list[str]:
    by_id = {n["id"]: n for n in nodes}
    issues: list[str] = []
    for scene in data["illustrations"]:
        missing = [f for f in FIELDS if f not in scene]
        if missing:
            issues.append(f"{scene.get('node_id')}: нет полей {missing}")
        elif scene["node_id"] not in by_id:
            issues.append(f"{scene['node_id']}: такого узла нет")
        else:
            issues += [f"{scene['node_id']}: {p}" for p in _scene_problems(scene, by_id[scene["node_id"]], templates, style)]
    drawn = {s.get("node_id") for s in data["illustrations"]}
    return issues + [f"{n}: нет иллюстрации" for n in by_id if n not in drawn]


def _brief(node: Mapping[str, Any]) -> dict[str, Any]:
    return {"node_id": node["id"], "title": node["short_title"], "main": node["layers"]["main"]["text"],
            "mechanism": node["layers"].get("mechanism", {}).get("text", ""),
            "claims": [{"id": c["id"], "text": c["text"]} for c in node["claims"]]}


def make_illustrations(
    provider: Provider, system: str, nodes: Sequence[Mapping], templates: Templates, style: Mapping[str, Any],
) -> tuple[list[dict], list[Reply]]:
    listed = "\n".join(f"- {t.SUMMARY}" for t in templates.values())
    prompt = f"# Шаблоны\n{listed}\n\n# Узлы\n{json.dumps([_brief(n) for n in nodes], ensure_ascii=False, indent=0)}"
    data, replies = ask_json(provider, system, prompt, lambda d: illustration_issues(d, nodes, templates, style))
    by_id = {n["id"]: n for n in nodes}
    good = [s for s in data["illustrations"] if all(f in s for f in FIELDS) and s["node_id"] in by_id
            and not _scene_problems(s, by_id[s["node_id"]], templates, style)]
    return good, replies


def records(scenes: Sequence[Mapping], nodes: Sequence[Mapping], templates: Templates, style: Mapping[str, Any], folder: Path) -> list[dict[str, Any]]:
    """Рисует SVG и возвращает записи по illustration.schema.json; спецификация сохраняется рядом."""
    folder.mkdir(parents=True, exist_ok=True)
    for stale in (*folder.glob("*.svg"), *folder.glob("*.json")):
        stale.unlink()
    by_id = {n["id"]: n for n in nodes}
    found: list[dict[str, Any]] = []
    for scene in scenes:
        template = templates[scene["template"]]
        number = sum(r["step_id"] == scene["node_id"] for r in found) + 1
        name = f"{scene['node_id'].split('.', 1)[-1]}_{number}"
        (folder / f"{name}.svg").write_text(render(template, scene["data"], style), encoding="utf-8")
        (folder / f"{name}.json").write_text(json.dumps(scene, ensure_ascii=False, indent=1), encoding="utf-8")
        pages = sorted({c["page_pdf"] for c in by_id[scene["node_id"]]["claims"] if c["id"] in scene["claim_ids"]})
        found = [*found, {
            "id": f"{scene['node_id']}.i{number}", "step_id": scene["node_id"], "node_id": scene["node_id"], "file": f"pictures/{name}.svg",
            "frame_class": template.FRAME_CLASS, "origin": "code_from_data" if _values(scene) else "code_from_model", "label": template.LABEL,
            "caption": scene["caption"], "alt": scene["alt"], "source": f"построено кодом по утверждениям главы, стр. {', '.join(map(str, pages))}",
            "claim_ids": list(scene["claim_ids"]), "prompt": None,
        }]
    return found
