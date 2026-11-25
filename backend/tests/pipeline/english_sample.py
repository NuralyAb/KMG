"""Короткая английская глава, написанная для тестов (не из книги), и подставная модель, которая собирает по ней слой."""

import json
from collections.abc import Sequence
from pathlib import Path

from glava.modules.llm.client import Reply

MD = """<!-- page 11 -->
Chapter 3 Pressure in a Wellbore and the Choice of Mud Weight 11

# 3.1 Hydrostatic pressure

The column of mud in a well exerts a hydrostatic pressure. It usually increases with depth, but it does not depend on the hole diameter.
A column 1,250 ft high may exert about 650 psi if the gradient is .52 psi/ft. This is the driller’s “first barrier”.

Figure 3.1 shows that pressure is never lower than the pressure at the surface.

$$p = 0.052 \\rho_m D \\tag{3.1}$$

Figure 3.1. Pressure versus depth for three muds.

━━━ FORMAT 6: XY PLOT / CHART WITH DATA ━━━

Ось X: давление, диапазон 0–12,5; ось Y: глубина.

----
<!-- page 12 -->
Chapter 3 Pressure in a Wellbore and the Choice of Mud Weight 12

Table 3.1 Mud weight and gradient
| Mud weight, lb/gal | Gradient, psi/ft | Depth limit, ft |
|---|---|---|
| 8.33 | 0.433 | 12,500 |
| 10.0 | 0.520 | 1,250,000 |

Formations with a permeability of 1.5×10³ md lose mud rapidly, whereas tight formations below 0.5 md take none at all. The perme-
ability of the filter cake is always smaller.

**Example 3.1** A well is 8,000 ft deep and is filled with 10.0 lb/gal mud. Find the pressure at the bottom.

Solution. p = 0.052 × 10.0 × 8,000 = 4,160 psi.
<!-- page 13 -->
Chapter 3 Pressure in a Wellbore and the Choice of Mud Weight 13

## Review Questions
3.1 Why must the mud weight be raised only gradually when a kick is suspected by the crew?

3.2 A gauge reads 2,600 psi at 5,000 ft. Estimate the mud weight that balances this reading.

## References

Smith, A. and Brown, B.: On the Weight of Drilling Muds, Journal of Imaginary Wells, 1984, 12, 101-117.
<!-- page 14 -->
Chapter 3 Pressure in a Wellbore and the Choice of Mud Weight 14

Green, C.: Notes on Filter Cakes, Transactions of an Imaginary Society, 1991, 5, 33-41.
"""
RANGES = [(11, 14)]

TEXT = {
    "The column of mud": "Столб раствора высотой 1250 футов может давать около 650 psi, если градиент 0,52 psi/фут; обычно давление растёт с глубиной и не зависит от диаметра.",
    "Figure 3.1 shows": "Давление никогда не ниже, чем на поверхности (рис. 3.1).",
    "$$p": "Давление равно 0,052, умноженному на плотность и глубину.",
    "Figure 3.1.": "На рисунке 3.1 — давление в зависимости от глубины.",
    "━━━": "По описанию рисунка, шкала давления идёт до 12,5.",
    "Table 3.1": "При плотности 8,33 фунта на галлон предел глубины 12 500 футов, при 10 — 1250000 футов.",
    "Formations with": "Пласты с проницаемостью 1,5·10³ мД быстро поглощают раствор, а плотные ниже 0,5 мД не поглощают совсем.",
    "**Example": "Скважина глубиной 8000 футов заполнена раствором 10 фунтов на галлон.",
    "Solution": "Давление на забое равно 4160 psi.",
}


def said(value: str) -> dict:
    return {"text": value, "by_model": True}


def node_answer(units: Sequence[dict]) -> dict:
    """Цитаты переписаны так, как это делает модель: прямые кавычки и слово без переноса."""
    def quote(text: str) -> str:
        return text[:300].replace("’", "'").replace("“", '"').replace("”", '"').replace("perme-\nability", "permeability")

    claims = [{"text": next(v for k, v in TEXT.items() if u["text"].startswith(k)), "kind": "observation", "page_pdf": u["page"], "unit_id": u["id"], "quote": quote(u["text"]),
               "source_kind": "text", "by_model": False, "needs_scan": False, "conditions": []} for u in units if any(u["text"].startswith(k) for k in TEXT)]
    tasks = [{"number": u["text"][:3], "page_pdf": u["page"], "text": "Почему плотность раствора повышают постепенно?" if u["text"].startswith("3.1") else
              "Манометр показывает 2600 psi на 5000 футах. Оцените плотность раствора.", "figure": None} for u in units if u["text"].startswith("3.")]
    examples = [{"page_pdf": 12, "condition": "Глубина 8000 футов, раствор 10 фунтов на галлон.", "steps": ["Перемножить 0,052, 10 и 8000."], "result": "4160 psi", "figure": None}]
    return {"layers": {k: said("Гидростатическое давление (hydrostatic pressure) растёт с глубиной.") for k in ("topic", "main", "mechanism", "practice", "nuances")} | {"deeper": []},
            "claims": claims, "misconception": None, "prerequisites": [], "terms_used": [], "needs_scan": [],
            "data_meaning": {"from_chapter": said("Глубина и давление."), "breaks": said("Нет данных о плотности."), "hypotheses": []},
            "it_analogy": {"text": "Как стек вызовов.", "breaks_where": "Стек не весит.", "by_model": True}, "now_practice": None, "inefficiency_lens": None,
            "decision_on_data": None, "worked_examples": examples, "book_tasks": tasks,
            "glossary": [{"term": "гидростатическое давление (hydrostatic pressure)", "definition": "Давление столба раствора."}]}


class Model:
    """Отвечает по системному промпту и запоминает все запросы."""

    name, model = "fake", "fake"

    def __init__(self, plan: dict, node=node_answer, essence: str = "Раствор давит на стенки скважины. Давление растёт с глубиной.") -> None:
        self.plan, self.node, self.essence = plan, node, essence
        self.requests: list[tuple[str, str]] = []

    def ask(self, system: str, prompt: str, files: Sequence[Path] = ()) -> Reply:
        self.requests.append((system, prompt))
        return Reply(json.dumps(self._answer(system, prompt), ensure_ascii=False), "fake", 1, 1, 0.0)

    def _answer(self, system: str, prompt: str) -> dict:
        if system.startswith("Ты методист"):
            return self.plan
        if system.startswith("Ты пишешь один узел"):
            return self.node(_units(prompt.partition("# Единицы узла\n\n")[2]))
        if system.startswith("Ты дополняешь"):
            nodes = json.JSONDecoder().raw_decode(prompt.partition("# Узлы\n")[2])[0]
            return {"nodes": [{"node_id": n["node_id"], "essence": self.essence, "short_title": "Давление в скважине", "procedure": [], "formulas": [],
                               "now_practice": None, "inefficiency_lens": None} for n in nodes]}
        raise AssertionError(f"неожиданный промпт: {system[:40]}")


def _units(text: str) -> list[dict]:
    found = []
    for part in text.partition("\n\n# Лист опечаток")[0].split("\n\n[p"):
        head, _, body = part.partition("\n")
        unit_id, kind, page = head.lstrip("[p").split("]")[0].split(" · ")
        found.append({"id": f"p{unit_id}", "kind": kind, "page": int(page.removeprefix("стр. ")), "text": body})
    return found


def plan_for(units: Sequence) -> dict:
    kept = [u.unit_id for u in units if u.kind != "heading" and not u.skippable]
    node = {"slug": "pressure", "title": "Гидростатическое давление раствора", "short_title": "Давление столба раствора", "why_here": "Опора для остального.",
            "difficulty": {"primary": "М", "secondary": None}, "threshold": False, "unit_ids": kept, "terms_introduced": ["гидростатическое давление (hydrostatic pressure)"]}
    return {"title": "Давление в скважине", "parts": [{"title": "Давление", "slugs": ["pressure"]}], "nodes": [node],
            "skipped": [{"unit_id": u.unit_id, "reason": "колонтитул, заголовок или литература"} for u in units if u.unit_id not in kept]}
