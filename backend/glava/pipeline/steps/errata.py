"""errata: сверка md со сканом."""

import logging
from concurrent.futures import ThreadPoolExecutor

from glava.modules.errata.api import make_errata, render_page
from glava.modules.layer.api import pages_of
from glava.modules.llm.api import Provider
from glava.pipeline.chapter import Chapter, write_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL
from glava.shared.json_files import save

log = logging.getLogger("glava")


def build_errata(chapter: Chapter, provider: Provider) -> None:
    """Сверка md со сканом. Без PDF этап пропускается: лист опечаток остаётся пустым."""
    if chapter.pdf is None or not chapter.pdf.exists():
        log.info("PDF главы не указан, лист опечаток пропущен")
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
