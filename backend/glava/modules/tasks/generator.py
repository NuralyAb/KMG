"""Задания курса: пять типов, ключ проверяется кодом, ответ держится на утверждениях узла."""

import ast
import json
import math
import os
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

import jsonschema

from glava.modules.drawing.api import evaluate
from glava.modules.llm.api import Provider, Reply, ask_json
from glava.shared.evidence import numbers_in, unsupported_numbers
from glava.shared.json_schemas import load_schema

MIN_TASKS = 15
MIN_TYPES = 4
GROUP = 4
GAP = re.compile(r"\{\{(\d+)\}\}")


FREE_LITERALS = frozenset({1.0, 2.0})  # 100 — только для ответа в процентах
MAX_EXPONENT = 30
MAX_TOLERANCE = 0.05
SCALED = re.compile(r"(\d+(?:[.,]\d+)?)\s*[·×*xх]\s*10\s*(?:\^?\{?\s*([-−⁻+⁺]?[\d⁰¹²³⁴-⁹]+)\}?)")
POWER = re.compile(r"(?<![\d·×*.,])10\s*(?:\^\{?\s*([-−⁻+⁺]?\d+)\}?|([⁻⁺]?[⁰¹²³⁴-⁹]+))")
NEGATIVE = re.compile(r"(?<![\w.,)])[-−–](\d+(?:[.,]\d+)?)")
FRACTION = re.compile(r"(?<![\d/.,])(\d+)\s*/\s*(\d+)(?![\d/])")
PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
ROUNDING = re.compile(r"\b(?:округл\w*|с точностью)\s+до\s+\S+", re.IGNORECASE)
PLAIN_POWER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺−", "0123456789-+-")
SIGNS = str.maketrans({"−": "-", "–": "-", "·": "*", "×": "*", "÷": "/", ":": "/"})


def _float(text: str) -> float:
    return float(text.replace(",", "."))


def stated_values(text: str) -> list[float]:
    """Величины, названные в условии: обычные числа, доли, степени десяти и проценты как доля."""
    found = [-_float(n) for n in NEGATIVE.findall(text)]
    plain = NEGATIVE.sub(" ", text)
    found += [_float(n) for n in numbers_in(plain)]
    powers = [(_float(m), p) for m, p in SCALED.findall(text)] + [(1.0, a or b) for a, b in POWER.findall(text)]
    found += [m * 10.0 ** e for m, p in powers if abs(e := int(p.translate(PLAIN_POWER))) <= MAX_EXPONENT]
    found += [float(a) / float(b) for a, b in FRACTION.findall(text) if float(b)]
    return found + [_float(n) / 100 for n in PERCENT.findall(plain)]


def _formula(task: Mapping) -> tuple[str, dict[str, float]]:
    text = re.sub(r"(?<=\d),(?=\d)", ".", task["formula"].translate(SIGNS))
    return unicodedata.normalize("NFKC", text), {unicodedata.normalize("NFKC", str(k)): float(v) for k, v in task["inputs"].items()}


def _formula_issue(formula: str, inputs: Mapping[str, float], is_percent: bool) -> str | None:
    nodes = list(ast.walk(ast.parse(formula.replace("^", "**"), mode="eval")))
    used = {n.id for n in nodes if isinstance(n, ast.Name)}
    unused = sorted(set(inputs) - used)
    if unused:
        return f"inputs не участвуют в формуле: {', '.join(unused)}"
    literals = {float(n.value) for n in nodes if isinstance(n, ast.Constant) and isinstance(n.value, int | float)}
    foreign = literals - FREE_LITERALS - ({100.0} if is_percent else set())
    return f"в формуле числа, которых нет в inputs: {', '.join(f'{x:g}' for x in sorted(foreign))}" if foreign else None


def _calc_issue(task: Mapping) -> str | None:
    """Ответ расчёта считает код: формула и её входные числа идут отдельно от текста."""
    formula, inputs = task.get("formula"), task.get("inputs")
    if not isinstance(formula, str) or not isinstance(inputs, Mapping) or not inputs or not all(
            isinstance(v, int | float) and not isinstance(v, bool) for v in inputs.values()):
        return "для расчёта нужны formula и inputs: имена и числа из условия"
    try:
        text, values = _formula(task)
        value, answer, tolerance = evaluate(text, values), float(task["answer"]), float(task["tolerance"])
        is_percent = "%" in str(task["unit"])
        problem = _formula_issue(text, values, is_percent)
        said = stated_values(_visible(task["prompt"]))
    except (ValueError, OverflowError, SyntaxError, RecursionError, MemoryError) as error:
        return f"formula: {error}"
    if problem:
        return problem
    if not math.isfinite(tolerance) or not 0 <= tolerance <= abs(value) * MAX_TOLERANCE:
        return f"tolerance от 0 до {MAX_TOLERANCE:.0%} ответа"
    if not math.isfinite(answer) or abs(value - answer) > tolerance + abs(value) * 1e-9:
        return f"по формуле получается {value:g}, а в answer {answer:g}"
    in_percent = {_float(n) for n in PERCENT.findall(task["prompt"])}
    if is_percent and "100" not in re.findall(r"\d+(?:\.\d+)?", text) and not any(abs(v) in in_percent for v in values.values()):
        return "ответ в процентах: умножьте долю на 100 или возьмите в inputs проценты из условия"
    missing = [k for k, v in values.items() if not any(math.isclose(v, n, rel_tol=1e-9) for n in said)]
    return f"чисел из inputs нет в условии: {', '.join(missing)}" if missing else None


def _visible(text: str) -> str:
    return re.sub(r"(?<=\d)[\s\u00a0\u202f](?=\d{3}(?!\d))", "", ROUNDING.sub(" ", GAP.sub(" ", text)))


def foreign_numbers(task: Mapping, node: Mapping) -> set[str]:
    """Числа условия, верного ответа и пояснения, которых нет в узле. Неверные варианты могут содержать любые числа."""
    right = task["answer"] if isinstance(task["answer"], list) else [task["answer"]]
    shown = [o["text"] for o in task.get("options") or [] if task["type"] == "order" or o["id"] in right]
    if task["type"] == "gap":
        shown += [str(a) for a in right]
    if task["type"] != "calc":  # пояснение расчёта показывает промежуточные числа, их проверяет формула
        shown.append(task["explanation"])
    source = json.dumps([[(c["text"], c.get("quote")) for c in node["claims"]], node.get("worked_examples"), node.get("book_tasks")], ensure_ascii=False)
    return unsupported_numbers(" ; ".join([_visible(task["prompt"]), *map(_visible, shown)]), _visible(source))


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
    return _calc_issue(task) if kind == "calc" else None


def task_issues(data: Mapping, nodes: Sequence[Mapping], env: Mapping[str, str] = os.environ) -> list[str]:
    """GLAVA_FREE_NUMBERS=1 разрешает в расчётах учебные числа, которых нет в книге."""
    validator = jsonschema.Draft202012Validator(load_schema("task"))
    problems = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:120]}" for e in validator.iter_errors({"chapter": "x", **data})]
    if problems:
        return problems
    claims = {n["id"]: {c["id"] for c in n["claims"]} for n in nodes}
    by_id = {n["id"]: n for n in nodes}
    issues: list[str] = []
    for task in data["tasks"]:
        if task["step_id"] not in claims:
            issues.append(f"{task['id']}: узла {task['step_id']} нет")
        elif not set(task["claim_ids"]) <= claims[task["step_id"]]:
            issues.append(f"{task['id']}: claim_ids не из узла {task['step_id']}")
        problem = _key_issue(task)
        if problem:
            issues.append(f"{task['id']}: {problem}")
        is_free = task["type"] == "calc" and env.get("GLAVA_FREE_NUMBERS") == "1"
        if task["step_id"] in by_id and not is_free and (foreign := foreign_numbers(task, by_id[task["step_id"]])):
            issues.append(f"{task['id']}: чисел нет в узле: {', '.join(sorted(foreign))}")
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
    return [t for t in data["tasks"] if isinstance(t, dict) and not task_issues({"tasks": [t]}, group)], replies
