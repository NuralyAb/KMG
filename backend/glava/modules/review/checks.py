"""Что код видит сам: цитата не на странице, чужие числа, чужие слова-условия. Это подсказки проверяющему, а не приговор."""

import re
from collections.abc import Mapping
from typing import Any

from glava.shared.evidence import find_quote_page, quote_on_page, unsupported_numbers

# начала слов, которыми задают условие, степень, направление и охват: подмена одного такого слова меняет смысл
CONDITION_STEMS = (
    "всегд", "никогд", "любо", "любы", "только", "исключительн", "универсальн", "однозначн", "полност", "невозможн",
    "умерен", "низк", "высок", "мал", "больш", "незначительн", "значительн", "слаб", "сильн", "резк", "плавн",
    "прям", "обратн", "линейн", "квадрат", "экспоненц", "рост", "раст", "увелич", "уменьш", "пада", "сниж", "повыш",
    "выше", "ниже", "меньше", "измер", "рассчит", "вычисл", "современ", "устарел",
)
WORD = re.compile(r"[а-яё]+")


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower().replace("ё", "е"))


def _stem(word: str) -> str | None:
    return next((s for s in CONDITION_STEMS if word.startswith(s)), None)


def foreign_condition_words(text: str, source: str) -> list[str]:
    """Слова-условия текста, у которых нет однокоренного слова в источнике: «умеренная» там, где у автора «низкая»."""
    present = {s for w in _words(source) if (s := _stem(w))}
    return list(dict.fromkeys(w for w in _words(text) if (s := _stem(w)) and s not in present))


def quick_notes(item: Mapping[str, Any], pages: Mapping[int, str]) -> list[str]:
    notes: list[str] = []
    page, quote = item.get("page_pdf"), item.get("quote")
    if quote and not quote_on_page(quote, pages.get(page, "")):
        real = find_quote_page(quote, pages)
        notes.append(f"цитата найдена на стр. {real}, указана {page}" if real else "цитаты нет в главе дословно")
    if page in pages:
        foreign = unsupported_numbers(item["text"], pages[page])
        notes += [f"чисел нет на стр. {page}: {', '.join(sorted(foreign))}"] if foreign else []
        words = foreign_condition_words(item["text"], f"{pages[page]} {quote or ''}")
        notes += [f"слов-условий нет на стр. {page}: {', '.join(words)}; сверить, не подменено ли условие автора"] if words else []
    return notes
