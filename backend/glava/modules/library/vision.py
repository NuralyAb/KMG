"""Страницы, которые код прочитал ненадёжно, читает модель по изображению. Прочитанное моделью остаётся с пометкой «сверить»."""

import logging
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from glava.modules.errata.api import render_page
from glava.modules.library.page import PAGE_MARK, Page
from glava.modules.llm.api import Provider, Reply, ask_json
from glava.shared.evidence import numbers_in

log = logging.getLogger(__name__)
METHOD = "vision"
MAX_SHOWN = 12
MIN_SHARE = 0.7


def page_issues(data: Any) -> list[str]:
    if not isinstance(data, Mapping) or not isinstance(data.get("md"), str) or not data["md"].strip():
        return ["нужен объект с непустой строкой md"]
    if PAGE_MARK.search(data["md"]):
        return ["в md не должно быть меток страниц"]
    unread = data.get("unreadable", [])
    return [] if isinstance(unread, list) and all(isinstance(u, str) for u in unread) else ["unreadable должен быть списком строк"]


def read_page(provider: Provider, system: str, page: Page, pdf: Path, folder: Path) -> tuple[Page, list[Reply]]:
    image = render_page(pdf, page.page, folder)
    try:
        data, replies = ask_json(provider, system, f"Страница {page.page}.", page_issues, attempts=2, files=(image,))
    except ValueError as error:  # не JSON: страница остаётся непрочитанной, остальные читаются дальше
        log.warning("страница %s не прочитана: %s", page.page, error)
        return page, []
    if page_issues(data):
        return page, replies
    read, had = data["md"].strip(), page.text.strip()
    if had and len(read) < len(had) * MIN_SHARE:
        # короткий пересказ вместо страницы потерял бы текст молча
        return replace(page, state="doubtful", reasons=(*page.reasons, "модель прочитала меньше, чем есть в файле: оставлен текст файла")), replies
    reasons = ["текст прочитала модель по изображению", *page.reasons]
    # слой PDF и чтение модели независимы: расхождение в числах показывает, куда смотреть человеку
    if had:
        only_model, only_file = (sorted(a - b)[:MAX_SHOWN] for a, b in ((numbers_in(read), numbers_in(had)), (numbers_in(had), numbers_in(read))))
        reasons += [f"чисел нет в исходном слое PDF: {', '.join(only_model)}"] if only_model else []
        reasons += [f"модель не прочитала числа из слоя PDF: {', '.join(only_file)}"] if only_file else []
    if data.get("unreadable"):
        reasons.append(f"не прочитано мест: {len(data['unreadable'])}")
    return Page(page.page, read, "doubtful", METHOD, tuple(reasons)), replies
