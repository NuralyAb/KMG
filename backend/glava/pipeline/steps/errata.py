"""errata: сверка md со сканом."""

import logging
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor

from glava.modules.errata.api import make_errata, not_caught, render_page
from glava.modules.source_text.api import kappa_suspects
from glava.modules.layer.api import pages_of
from glava.modules.llm.api import Provider
from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import save

log = logging.getLogger("glava")


def build_symbols(chapter: Chapter, entries: Sequence[Mapping] = ()) -> list[dict]:
    """Бесплатное правило: ϰ, прочитанная как π или k. Места, которых нет в листе модели, — в <глава>.symbols.json, его читают layer и проверки."""
    found = kappa_suspects(chapter.source_units)
    missed = not_caught(found, entries)
    save(chapter.errata_file.with_suffix(".symbols.json"), {"chapter": chapter.chapter_id, "entries": missed})
    if found:
        log.warning("правило ϰ: %s мест, где вместо ϰ стоит π или k; лист модели поймал %s, остальные %s добавлены в %s",
                    len(found), len(found) - len(missed), len(missed), chapter.errata_file.with_suffix(".symbols.json").name)
    return missed


def build_errata(chapter: Chapter, provider: Provider) -> None:
    """Сверка md со сканом. Без PDF модель не спрашивается: остаётся только бесплатное правило ϰ."""
    if chapter.pdf is None or not chapter.pdf.exists():
        log.info("PDF главы не указан, лист опечаток пропущен")
        build_symbols(chapter)
        return
    # сверяется текст распознавателя: прочтение рисунков этапа figures уже сверено со сканом
    pages, prompt = pages_of(chapter.source_units), prompt_file("errata", chapter.is_english)
    images = {n: render_page(chapter.pdf, n, chapter.work / "scans") for n in pages}
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda n: make_errata(provider, prompt, n, pages[n], images[n]), pages))
    entries = [e for found, _ in results for e in found]
    save(chapter.errata_file, {"chapter": chapter.chapter_id, "entries": entries})
    write_metrics(chapter, "errata", len(pages), [r for _, rs in results for r in rs])
    log.info("лист опечаток: %s записей, из них подозрительных мест издания: %s", len(entries), sum(e["kind"] == "suspect" for e in entries))
    build_symbols(chapter, entries)
