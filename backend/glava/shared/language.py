"""Язык текста: русский или английский. Русские главы этими правилами не затрагиваются.

Одной латиницы мало: в русских книгах на ней формулы, а сбой распознавания превращает русский абзац в набор латинских букв.
Поэтому нужны английские служебные слова.
"""

import re
from functools import lru_cache

MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)|\\\[.*?\\\]|\\[a-zA-Z]+", re.DOTALL)
LATIN = re.compile(r"(?<![^\W_])[A-Za-z]{3,}(?![^\W_])")
CYRILLIC = re.compile(r"[А-Яа-яЁё]{3,}")
FUNCTION = re.compile(
    r"(?<!\w)(?:the|of|and|is|are|was|were|in|to|for|with|that|by|from|as|at|be|which|this|an|it|on|or|not|if|has|have|than|when)(?!\w)", re.IGNORECASE)
MIN_WORDS = 2
MIN_FUNCTION = 3
MIN_SHARE = 0.05


def _counts(text: str) -> tuple[int, int, int]:
    plain = MATH.sub(" ", text)
    return len(LATIN.findall(plain)), len(CYRILLIC.findall(plain)), len(FUNCTION.findall(plain))


@lru_cache(maxsize=2048)
def is_english(text: str) -> bool:
    """Текст английский: латинских слов вне формул больше, чем русских, и среди них есть служебные."""
    latin, cyrillic, function = _counts(text)
    return latin >= MIN_WORDS and latin > cyrillic and function >= max(1, latin * MIN_SHARE)


@lru_cache(maxsize=512)
def has_english(text: str) -> bool:
    """В тексте есть английская проза: и страница с русским описанием рисунка, и утверждение вместе с английской цитатой."""
    latin, cyrillic, function = _counts(text)
    return is_english(text) or function >= max(MIN_FUNCTION, (latin + cyrillic) * MIN_SHARE)


def is_untranslated(text: str, min_words: int = 3) -> bool:
    """Текст слоя остался на языке книги: русских слов нет, а латинских хотя бы min_words."""
    latin, cyrillic, _ = _counts(text)
    return latin >= min_words and cyrillic == 0
