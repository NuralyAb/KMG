"""Сцены: модель заполняет спецификацию, проверяет и рисует код. Предметные шаблоны лежат в доменном пакете.

Шаблон — модуль с именами SUMMARY (подсказка модели), SCHEMA, LABEL, FRAME_CLASS, check(data, style), draw(data, style).
"""

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema

from glava.scenes import bars, compare, flow, plot
from glava.scenes.canvas import PAD, W, rect, text, wrap

__all__ = ["load_templates", "render", "scene_issues", "wrap"]

GENERIC = {"flow": flow, "compare": compare, "plot": plot, "bars": bars}
BADGE_H = 40


def load_templates(folder: Path) -> dict[str, ModuleType]:
    found: dict[str, ModuleType] = dict(GENERIC)
    for file in sorted(folder.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"domain_template_{file.stem}", file)
        if spec is None or spec.loader is None:
            raise ImportError(f"шаблон {file} не читается")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        found = {**found, file.stem: module}
    return found


def scene_issues(template: ModuleType, data: Mapping[str, Any], style: Mapping[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(template.SCHEMA)
    problems = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:140]}" for e in validator.iter_errors(data)]
    return problems or template.check(data, style)


def render(template: ModuleType, data: Mapping[str, Any], style: Mapping[str, Any]) -> str:
    body, height = template.draw(data, style)
    total = height + BADGE_H + PAD
    width = 14 * len(template.LABEL) + 24
    badge = (rect(PAD, height + 4, width, BADGE_H - 6, style["provenance"][template.LABEL], radius=6)
             + text(PAD + width / 2, height + 29, template.LABEL, "#FFFFFF", "middle"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {total:.0f}" width="{W}" height="{total:.0f}" '
            f'font-family="{style["fonts"]["ui"]}, sans-serif" role="img">'
            f'{rect(0, 0, W, total, style["background"], radius=12)}{body}{badge}</svg>')
