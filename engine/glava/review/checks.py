"""Что код видит сам: цитата не на странице, чужие числа. Это подсказки проверяющему, а не приговор."""

from collections.abc import Mapping
from typing import Any

from glava.verify import find_quote_page, quote_on_page, unsupported_numbers


def quick_notes(item: Mapping[str, Any], pages: Mapping[int, str]) -> list[str]:
    notes: list[str] = []
    page, quote = item.get("page_pdf"), item.get("quote")
    if quote and not quote_on_page(quote, pages.get(page, "")):
        real = find_quote_page(quote, pages)
        notes.append(f"цитата найдена на стр. {real}, указана {page}" if real else "цитаты нет в главе дословно")
    if page in pages:
        foreign = unsupported_numbers(item["text"], pages[page])
        notes += [f"чисел нет на стр. {page}: {', '.join(sorted(foreign))}"] if foreign else []
    return notes
