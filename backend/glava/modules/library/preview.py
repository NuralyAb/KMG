"""Картинки страниц: человек сверяет извлечённый текст с книгой, не открывая её отдельно."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)
DPI = 100
POINTS = 72
MAX_SIDE_PX = 2000


def preview_file(folder: Path, page: int) -> Path:
    return folder / f"p{page:05d}.png"


def make_previews(pdf: Path, folder: Path) -> int:
    """Страница, которую не удалось нарисовать, остаётся без картинки: текст от этого не зависит."""
    import pymupdf

    folder.mkdir(parents=True, exist_ok=True)
    made = 0
    with pymupdf.open(pdf) as document:
        for number, page in enumerate(document, start=1):
            side = max(page.rect.width, page.rect.height, 1)
            scale = min(DPI / POINTS, MAX_SIDE_PX / side)
            try:
                page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(preview_file(folder, number))
                made += 1
            except (RuntimeError, ValueError) as error:
                log.warning("страница %s: картинка не нарисована: %s", number, error)
    return made
