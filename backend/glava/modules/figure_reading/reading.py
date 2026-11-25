"""Рисунки главы читает модель по изображению страницы. Прочтение заменяет описание распознавателя, расхождения с ним идут в лист опечаток.

Прочтение — тоже слова модели: единица остаётся «описанием распознавателя» (by_recogniser), её числа приблизительны.
"""

import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from glava.modules.llm.api import Provider, Reply, ask_json
from glava.modules.source_text.api import Unit
from glava.shared.evidence import quote_on_page

log = logging.getLogger(__name__)
LISTS = ("axes", "curves", "regions", "legend", "numbers", "mismatches", "unreadable")
MAX_MISMATCH = 200
ROUGH = ("≈", "~", "около", "примерно")
OWN_SUFFIX = "f"  # единица прочтения у рисунка без описания: p032.04 -> p032.04f


@dataclass(frozen=True)
class FigurePage:
    """Страница с рисунками: описания распознавателя и подписи на ней, подписи соседних страниц."""

    page: int
    descriptions: tuple[Unit, ...]
    captions: tuple[Unit, ...]
    nearby: tuple[Unit, ...]

    @property
    def prompt(self) -> str:
        def block(title: str, units: Sequence[Unit]) -> str:
            return f"\n\n## {title}\n\n" + "\n\n".join(f"[{u.unit_id}]\n{u.text}" for u in units) if units else ""

        return (f"# Страница {self.page}" + block("Описания распознавателя", self.descriptions) + block("Подписи на этой странице", self.captions)
                + block("Подписи на соседних страницах", self.nearby))


def is_caption(unit: Unit) -> bool:
    return unit.kind == "figure" and not unit.by_recogniser


def figure_pages(units: Sequence[Unit]) -> list[FigurePage]:
    """Страницы, где есть описание распознавателя или подпись рисунка."""
    pages = sorted({u.page_pdf for u in units if u.by_recogniser or is_caption(u)})
    found = []
    for page in pages:
        descriptions = tuple(u for u in units if u.page_pdf == page and u.by_recogniser)
        captions = tuple(u for u in units if u.page_pdf == page and is_caption(u))
        nearby = tuple(u for u in units if abs(u.page_pdf - page) == 1 and is_caption(u))
        found.append(FigurePage(page, descriptions, captions, nearby))
    return found


def page_key(provider: Provider, system: str, found: FigurePage, image: Path) -> str:
    """Тот же вопрос той же модели по той же картинке не задаётся второй раз."""
    parts = [provider.name, provider.model, system, found.prompt, hashlib.sha256(image.read_bytes()).hexdigest()]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()[:32]


def _texts(value: Any, fields: Sequence[str]) -> bool:
    if fields == ():
        return isinstance(value, str)
    return isinstance(value, Mapping) and all(isinstance(value.get(f, ""), str) for f in fields)


ITEM_FIELDS: Mapping[str, tuple[str, ...]] = {
    "axes": ("name", "where", "scale", "ticks"), "curves": ("label", "meaning", "behaviour"), "regions": ("label", "meaning"),
    "legend": (), "numbers": ("what", "value"), "mismatches": ("recogniser", "scan", "note"), "unreadable": (),
}


def mismatch_issue(item: Mapping[str, Any], description: str) -> str | None:
    said, seen = str(item.get("recogniser") or ""), str(item.get("scan") or "")
    if not said.strip() or not seen.strip():
        return "в mismatches нужны recogniser и scan"
    if len(said) > MAX_MISMATCH or not quote_on_page(said, description):
        return f"«{said[:60]}» нет в описании распознавателя дословно (8–{MAX_MISMATCH} знаков)"
    return "scan совпадает с recogniser" if said.strip() == seen.strip() else None


def _figure_issues(figure: Any, found: FigurePage) -> list[str]:
    if not isinstance(figure, Mapping):
        return ["прочтение рисунка должно быть объектом"]
    uid = figure.get("unit_id")
    own = {u.unit_id: u for u in (*found.descriptions, *found.captions)}
    if uid not in own:
        return [f"unit_id {uid!r}: нет такого описания или подписи на этой странице"]
    issues = []
    if figure.get("caption_unit") is not None and figure["caption_unit"] not in {u.unit_id for u in (*found.captions, *found.nearby)}:
        issues.append(f"{uid}: caption_unit {figure['caption_unit']!r} — не подпись этой или соседней страницы")
    if not isinstance(figure.get("what"), str) or not figure["what"].strip():
        issues.append(f"{uid}: нужен what")
    for name, fields in ITEM_FIELDS.items():
        items = figure.get(name, [])
        if not isinstance(items, list) or not all(_texts(i, fields) for i in items):
            issues.append(f"{uid}: {name} — список " + (f"объектов с полями {fields}" if fields else "строк"))
    if not own[uid].by_recogniser and figure.get("mismatches"):
        issues.append(f"{uid}: у рисунка без описания распознавателя mismatches пустой")
    elif not issues:
        issues += [f"{uid}: {i}" for m in figure.get("mismatches", []) if (i := mismatch_issue(m, own[uid].text))]
    return issues


def reading_issues(data: Any, found: FigurePage) -> list[str]:
    if not isinstance(data, Mapping) or not isinstance(data.get("figures"), list):
        return ["нужен объект с массивом figures"]
    issues = [i for f in data["figures"] for i in _figure_issues(f, found)]
    ids = [f.get("unit_id") for f in data["figures"] if isinstance(f, Mapping)]
    issues += [f"у {uid} больше одного прочтения" for uid in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    issues += [f"описание {u.unit_id} не прочитано" for u in found.descriptions if u.unit_id not in ids]
    named = {*ids, *(f.get("caption_unit") for f in data["figures"] if isinstance(f, Mapping))}
    absent = data.get("not_here", [])
    if not isinstance(absent, list):
        return [*issues, "not_here — список id подписей"]
    issues += [f"подпись {u.unit_id}: укажи её в caption_unit или в not_here" for u in found.captions if u.unit_id not in named and u.unit_id not in absent]
    return issues


def read_figures(provider: Provider, system: str, found: FigurePage, image: Path) -> tuple[list[dict], list[Reply]]:
    """Прочтения рисунков страницы. Неверное прочтение отбрасывается: у рисунка остаётся описание распознавателя."""
    try:
        data, replies = ask_json(provider, system, found.prompt, lambda d: reading_issues(d, found), attempts=2, files=(image,))
    except ValueError as error:  # не JSON: остальные страницы читаются дальше
        log.warning("рисунки страницы %s не прочитаны: %s", found.page, error)
        return [], []
    own = {u.unit_id: u for u in (*found.descriptions, *found.captions)}
    kept = []
    for figure in data.get("figures", []) if isinstance(data, Mapping) else []:
        if not isinstance(figure, Mapping) or figure.get("unit_id") not in own:
            continue
        unit = own[figure["unit_id"]]
        figure = {**figure, "mismatches": [m for m in figure.get("mismatches", []) if isinstance(m, Mapping) and mismatch_issue(m, unit.text) is None]
                  if unit.by_recogniser else []}
        if _figure_issues(figure, found):
            log.warning("рисунок %s не прочитан: %s", unit.unit_id, "; ".join(_figure_issues(figure, found))[:200])
            continue
        kept.append({**figure, "page": found.page, "source": unit.text})
    return kept, replies


def _rough(value: str) -> str:
    return value if value.strip().startswith(ROUGH) else f"≈ {value.strip()}"


def reading_text(figure: Mapping[str, Any]) -> str:
    """Прочтение одним блоком текста: его цитирует слой."""
    title = f"Рисунок {figure['figure']}" if figure.get("figure") else "Рисунок"
    lines = [f"━━━ {title}, прочитан моделью по изображению страницы {figure['page']}; числа сняты глазом, приблизительно ━━━", figure["what"].strip()]

    def section(name: str, rows: Iterable[str]) -> None:
        rows = [r for r in rows if r.strip()]
        if rows:
            lines.extend(["", f"{name}:", *(f"- {r}" for r in rows)])

    def joined(*parts: Any) -> str:
        return "; ".join(str(p).strip() for p in parts if str(p or "").strip())

    def row(head: Any, body: str) -> str:
        head = str(head or "").strip()
        return f"{head}: {body}" if head and body else head or body

    section("Оси и шкалы", (row(f"{a.get('name', '')}" + (f" ({where})" if (where := joined(a.get("where"), a.get("scale"))) else ""), str(a.get("ticks") or "").strip())
                            for a in figure.get("axes", [])))
    section("Кривые", (row(c.get("label"), joined(c.get("meaning"), c.get("behaviour"))) for c in figure.get("curves", [])))
    section("Области", (row(r.get("label"), str(r.get("meaning") or "").strip()) for r in figure.get("regions", [])))
    section("Условные обозначения", figure.get("legend", []))
    section("Числа, снятые с рисунка глазом (приблизительно)", (f"{n.get('what', '')}: {_rough(n.get('value', ''))}" for n in figure.get("numbers", []) if n.get("value")))
    section("Не разобрать", figure.get("unreadable", []))
    return "\n".join(lines)


def with_readings(units: Sequence[Unit], readings: Iterable[Mapping[str, Any]]) -> list[Unit]:
    """Описание распознавателя заменяется прочтением; у рисунка без описания прочтение встаёт после подписи.

    Прочтение старого текста (md изменился) не применяется: иначе оно легло бы не на тот рисунок.
    """
    by_unit = {r["unit_id"]: r for r in readings}
    out: list[Unit] = []
    stale = []
    for unit in units:
        reading = by_unit.get(unit.unit_id)
        if reading is not None and reading.get("source") != unit.text:
            stale.append(unit.unit_id)
            reading = None
        if reading is None:
            out.append(unit)
        elif unit.by_recogniser:
            out.append(replace(unit, text=reading_text(reading)))
        else:
            out.extend([unit, Unit(f"{unit.unit_id}{OWN_SUFFIX}", "figure", unit.page_pdf, reading_text(reading), by_recogniser=True, needs_scan=unit.needs_scan)])
    if stale:
        log.warning("прочтения рисунков устарели, текст главы изменился: %s; повторите glava figures", ", ".join(stale))
    return out


def figure_errata(readings: Iterable[Mapping[str, Any]]) -> list[dict]:
    """Расхождения описания распознавателя со сканом — записи recognition листа опечаток."""
    return [{"page": r["page"], "md": m["recogniser"], "scan": m["scan"], "kind": "recognition",
             "note": "; ".join(filter(None, [f"рис. {r['figure']}" if r.get("figure") else "рисунок", (m.get("note") or "").strip(), "прочитано моделью по скану"]))}
            for r in readings for m in r.get("mismatches", [])]
