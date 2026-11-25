"""Английский источник: как читать его числа и как вернуть цитате точный вид страницы."""

import re

# 12,500 и 12{,}500 — двенадцать с половиной тысяч; 0,125 английской записью не бывает
GROUPED = re.compile(r"(?<![\w.,])[1-9]\d{0,2}(?:(?:,|\{,\}|\\,)\d{3})+(?![\d,]*\d)")
SPACED = re.compile(r"(?<=\d)[ \u00a0\u2009\u202f](?=\d{3}(?!\d))")
LEADING_POINT = re.compile(r"(?<![\w.,)])\.(?=\d)")
MIDDLE_POINT = re.compile(r"(?<![\w.])0·(?=\d)")
EXPONENT = re.compile(r"(?<=\d)[eE]([-+−–]?\d+)(?!\w)")
TIMES = re.compile(r"(?<=\d)[xX](?=10\D)")
POWER = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
PLAIN_POWER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")

PLAIN = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'", "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
                       "–": "-", "—": "-", "−": "-", "\u2011": "-", "\u2010": "-", "×": "x", "…": "..."})
BREAK = re.compile(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[a-z])|\u00ad\s*")
# \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0432\u0430\u0442\u0435\u043b\u044c \u044d\u043a\u0440\u0430\u043d\u0438\u0440\u0443\u0435\u0442 \u0437\u043d\u0430\u043a\u0438 \u0440\u0430\u0437\u043c\u0435\u0442\u043a\u0438: \$0.75, 15\%; \u043c\u043e\u0434\u0435\u043b\u044c \u0446\u0438\u0442\u0438\u0440\u0443\u0435\u0442 \u0438\u0445 \u0431\u0435\u0437 \u043e\u0431\u0440\u0430\u0442\u043d\u043e\u0439 \u0447\u0435\u0440\u0442\u044b
ESCAPE = re.compile(r"\\(?=[$%&#_])")


def _read(line: str) -> str:
    line = GROUPED.sub(lambda m: re.sub(r"\D", "", m.group()), line)
    line = MIDDLE_POINT.sub("0.", LEADING_POINT.sub("0.", line))
    line = TIMES.sub(" ", line)
    line = EXPONENT.sub(r" 10 \1", line)
    return POWER.sub(lambda m: f"{m.group()} {m.group().translate(PLAIN_POWER)}", line)


def plain_numbers(source: str) -> list[str]:
    """Прочтения текста, по которым число считается стоящим в источнике. Русские строки (описание рисунка) читаются и по-русски."""
    read = "\n".join(map(_read, source.splitlines()))
    russian = "\n".join(line for line in source.splitlines() if CYRILLIC.search(line))
    return [read, SPACED.sub("", read), russian]


def _letters(text: str) -> tuple[str, list[int]]:
    """Текст без пробелов и переносов, с обычными кавычками и дефисами; для каждого знака — его место в исходном тексте."""
    hidden = {i for pattern in (BREAK, ESCAPE) for m in pattern.finditer(text) for i in range(*m.span())}
    letters: list[str] = []
    places: list[int] = []
    for i, char in enumerate(text):
        if char.isspace() or i in hidden:
            continue
        for plain in char.translate(PLAIN).casefold():
            letters.append(plain)
            places.append(i)
    return "".join(letters), places


def exact_quote(quote: str, text: str) -> str | None:
    """Кусок текста, который модель переписала с другими кавычками, дефисами или без переноса слова."""
    needle, _ = _letters(quote)
    letters, places = _letters(text)
    start = letters.find(needle) if needle else -1
    return text[places[start]:places[start + len(needle) - 1] + 1] if start >= 0 else None
