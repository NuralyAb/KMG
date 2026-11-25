"""figures: рисунки главы читает модель по изображению страницы, до слоя."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from glava.modules.errata.api import render_page
from glava.modules.figure_reading.api import (
    FigurePage,
    figure_errata,
    figure_pages,
    page_key,
    read_figures,
)
from glava.modules.llm.api import Provider, Reply
from glava.pipeline.chapter import Chapter, figures_file, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import read_or, save

log = logging.getLogger("glava")


def build_figures(chapter: Chapter, provider: Provider, pages: set[int] | None = None) -> list[dict[str, Any]]:
    """Прочтения рисунков в work/<глава>/figures.json, расхождения с распознавателем — в лист опечаток <глава>.figures.json.

    Страница, чей вопрос не изменился, не спрашивается снова: прочтение берётся из figures.json.
    pages — прочитать только эти страницы (проба); остальные прочтения файла сохраняются.
    """
    if chapter.pdf is None or not chapter.pdf.exists():
        log.info("PDF главы не указан, рисунки остаются с описанием распознавателя")
        return []
    system = prompt_file("figures", chapter.is_english)
    found = [f for f in figure_pages(chapter.source_units) if pages is None or f.page in pages]
    images = {f.page: render_page(chapter.pdf, f.page, chapter.work / "scans") for f in found}
    keys = {f.page: page_key(provider, system, f, images[f.page]) for f in found}
    saved = {p["page"]: p for p in read_or(figures_file(chapter), {"pages": []})["pages"]}
    fresh = [f for f in found if saved.get(f.page, {}).get("key") != keys[f.page]]

    def one(page: FigurePage) -> tuple[int, list[dict], list[Reply]]:
        return page.page, *read_figures(provider, system, page, images[page.page])

    with ThreadPoolExecutor(PARALLEL) as pool:
        asked = list(pool.map(one, fresh))
    # страница без прочтений не кэшируется: при повторе её спросят снова
    saved |= {page: {"page": page, "key": keys[page], "figures": figures} for page, figures, _ in asked if figures}
    if pages is None:
        saved = {page: entry for page, entry in saved.items() if page in keys}
    readings = [r for page in sorted(saved) for r in saved[page]["figures"]]
    save(figures_file(chapter), {"chapter": chapter.chapter_id, "pages": [saved[p] for p in sorted(saved)]})
    errata = figure_errata(readings)
    save(chapter.errata_file.with_suffix(".figures.json"), {"chapter": chapter.chapter_id, "entries": errata})
    replies = [r for _, _, rs in asked for r in rs]
    if asked:
        write_metrics(chapter, "figures", sum(len(f) for _, f, _ in asked), replies)
    missed = [f.page for f in found if f.page not in saved]
    log.info("рисунки: страниц %s, спрошено %s, прочтений %s, расхождений с распознавателем %s, не прочитаны страницы: %s, $%.2f",
             len(found), len(fresh), len(readings), len(errata), ", ".join(map(str, missed)) or "нет", sum(r.cost_usd for r in replies))
    return readings
