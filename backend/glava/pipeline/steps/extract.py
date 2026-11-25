"""extract: загруженный файл → страницы md."""

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from glava.modules.library.api import (
    extract_pages,
    load_source,
    make_previews,
    read_page,
    to_md,
)
from glava.modules.metrics.api import append_metrics
from glava.pipeline.prompts import prompt_file
from glava.pipeline.runtime import PARALLEL, open_provider
from glava.shared.json_files import save
from glava.shared.paths import workspace

log = logging.getLogger("glava")


def build_extract(source_id: str, with_model: bool) -> None:
    """Загруженный файл -> страницы md и отчёт, каким страницам можно верить."""
    source = load_source(workspace(), source_id)
    pages = extract_pages(source.original, source.kind, source.folder / "scan.pdf")
    if source.pdf is not None:
        make_previews(source.pdf, source.folder / "preview")
    weak = [p for p in pages if p.state in ("scan", "doubtful")]
    if with_model and source.pdf is not None and weak:
        provider, prompt = open_provider(), prompt_file("extract")
        pdf, folder = source.pdf, source.folder / "scans"
        with ThreadPoolExecutor(PARALLEL) as pool:
            read_again = {p.page: (p, rs) for p, rs in pool.map(lambda p: read_page(provider, prompt, p, pdf, folder), weak)}
        pages = [read_again[p.page][0] if p.page in read_again else p for p in pages]
        replies = [r for _, rs in read_again.values() for r in rs]
        append_metrics(source_id, "extract", len(weak), replies)
        log.info("моделью прочитано страниц: %s, $%.2f", sum(p.method == "vision" for p in pages), sum(r.cost_usd for r in replies))
    source.text.write_text(to_md(pages), encoding="utf-8", newline="\n")
    save(source.pages, {"source": source_id, "pages": [p.record() for p in pages]})
    states = Counter(p.state for p in pages)
    log.info("страниц %s: надёжных %s, сверить %s, без текста %s, пустых %s", len(pages), states["text"], states["doubtful"], states["scan"], states["empty"])
