"""Сценарий озвученного разбора шага: фразы берутся из слоя дословно, модель не нужна."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«\d$(])")
SHORT = re.compile(r"(?:^|[\s(])(?:рис|табл|стр|гл|см|ср|др|пр|т|е|п|д|напр)\.$", re.IGNORECASE)
WORD = re.compile(r"[а-яёa-z]{4,}", re.IGNORECASE)
STEM = 6
MIN_OVERLAP = 2
MAX_WORDS = 105
MIN_BEATS = 2
MIN_PHRASE_WORDS = 3
# ссылка на рисунок или формулу вслух бесполезна: её не видно в кадре
ASIDE = re.compile(r"\s*\((?:см\.|рис\.|табл\.|формул|пример)[^)]*\)")
POINTS_ELSEWHERE = re.compile(r"\b(?:рис|табл|см|стр)\.|формул\w*\s*\(|\(\d+\)|\\|\$|пример\w*\s+\d", re.IGNORECASE)
OPERATORS = (("≥", " не меньше "), ("≤", " не больше "), (">", " больше "), ("<", " меньше "), ("=", " равно "), ("≈", " примерно равно "), ("→", ", "), ("−", " минус "))
BOOK_WORDS = ((re.compile(r"\b([Нн]а|[Вв]) рис\."), r"\1 рисунке"), (re.compile(r"\b([Нн]а|[Вв]) табл\."), r"\1 таблице"), (re.compile(r"\b([Пп]о) рис\."), r"\1 рисунку"),
              (re.compile(r"\b([Сс]|из|для) рис\."), r"\1 рисунка"), (re.compile(r"\bрис\."), "рисунок"), (re.compile(r"\bтабл\."), "таблица"))
STARS = ((re.compile(r"\*\*"), " с двумя звёздочками"), (re.compile(r"\*"), " со звёздочкой"))
# что голос не прочтёт: латиница, греческие буквы, индексы, знаки действий
FUNCTION = re.compile(r"\s*=\s*f\(([^()]+)\)")
# фраза держится за предыдущую: если ту пропустили, смысл теряется
LEANS = re.compile(r"(?:Затем|Поэтому|Тогда|Там|Это|Этот|Эта|Эти|Он|Она|Они|Его|Её|Их|Для этого|При этом|Зато|Такой|Такая|Такие|Вторая|Второй|Отсюда|Значит|Получается|Так|Ставшее|У него|Сначала|В нём|Но|Остальн\w+|Ещё|Иначе|Дальше|Здесь|Кажд\w+|Нужна и)\b")
# речь о самой книге и слое, а не о предмете
ABOUT_BOOK = re.compile(r"выданн|единиц\w+ (?:главы|книги|формул)|част[иь] главы|в главе (?:не|нет|она)|пояснение модели|опечатк|\bузел\b|задач\w+ \d|в шагах|таблиц\w+ \d|дан[аоы] в |книга ", re.IGNORECASE)
ABOUT_NODE = re.compile(r"узел", re.IGNORECASE)
UNREADABLE = re.compile(r"[A-Za-zͰ-Ͽ_\\$^{}|²³·×/∑]")


@dataclass(frozen=True)
class Beat:
    kind: str
    text: str
    say: str
    claim_id: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class Reader:
    """Как читать обозначения и где ставить ударение: таблицы pronunciation.md доменного пакета."""

    short: Mapping[str, str]
    stress: Mapping[str, str]

    def say(self, text: str) -> str | None:
        for name in sorted(self.short, key=len, reverse=True):
            text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", self.short[name], text)
        for pattern, words in BOOK_WORDS:
            text = pattern.sub(words, text)
        text = FUNCTION.sub(lambda m: f" от {m[1]}", text)
        for sign, words in OPERATORS:
            text = text.replace(sign, words)
        for pattern, words in STARS:
            text = pattern.sub(words, text)
        # дробь из двух обозначений: «ро пэ / ро гэ эл»
        text = re.sub(r"(?<=[а-яё])\s*/\s*(?=[а-яё])", " к ", text)
        if UNREADABLE.search(text):
            return None
        return re.sub(r"\s+", " ", re.sub(r"\w+", self._stressed, text)).strip()

    def _stressed(self, match: re.Match[str]) -> str:
        word = match.group()
        marked = self.stress.get(word.lower())
        if not marked:
            return word
        return marked[0].upper() + marked[1:] if word[0].isupper() else marked


def reader(tables: str) -> Reader:
    """Строки «пишется | читается | расшифровка» и «слово | с ударением»."""
    short: dict[str, str] = {}
    stress: dict[str, str] = {}
    for line in tables.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] != "Пишется" and not set(cells[0]) <= {"-", " "}:
            names, sounds = [c.strip() for c in cells[0].split(",")], [c.strip() for c in cells[1].split(",")]
            if len(names) == len(sounds):
                short = {**short, **dict(zip(names, sounds, strict=True))}
        elif len(cells) == 2 and "́" in cells[1]:
            stress = {**stress, cells[0].lower(): cells[1]}
    return Reader(short, stress)


def _stems(text: str) -> set[str]:
    return {w.casefold()[:STEM] for w in WORD.findall(text)}


def nearest_claim(text: str, claims: Sequence[Mapping]) -> Mapping | None:
    """Утверждение, с которым у фразы больше всего общих слов; слабое сходство не считается."""
    words = _stems(text)
    score, claim = max(((len(words & _stems(c["text"])), c) for c in claims), key=lambda x: x[0], default=(0, None))
    return claim if score >= MIN_OVERLAP else None


def sentences(text: str) -> list[str]:
    """Точка после «рис.» предложение не заканчивает."""
    found: list[str] = []
    for piece in SENTENCE.split(text.strip()):
        found = [*found[:-1], f"{found[-1]} {piece}"] if found and SHORT.search(found[-1]) else [*found, piece]
    return [s for s in found if s]


def _sentences(node: Mapping) -> list[tuple[str, str]]:
    layers = node["layers"]
    return [(kind, s) for kind, key in (("main", "main"), ("how", "mechanism"), ("how", "practice")) for s in sentences(layers.get(key, {}).get("text", ""))]


def write_script(node: Mapping[str, Any], read: Reader) -> tuple[list[Beat], list[str]]:
    """Фразы разбора и то, что пришлось пропустить. Суть идёт первой и целиком, объяснение — пока хватает времени."""
    beats: list[Beat] = []
    skipped: list[str] = []
    words = 0
    last = ""
    for kind, sentence in _sentences(node):
        text = ASIDE.sub("", sentence)
        if kind == "how" and words >= MAX_WORDS:
            break
        is_lost = bool(skipped) and skipped[-1] is last and bool(LEANS.match(text))
        last = sentence
        # суть звучит целиком, даже если ссылается на рисунок книги; объяснение — только то, что понятно на слух
        is_bad = is_lost or bool(ABOUT_NODE.search(text)) or len(text.split()) < MIN_PHRASE_WORDS or (kind == "how" and bool(POINTS_ELSEWHERE.search(text) or ABOUT_BOOK.search(text)))
        say = None if is_bad else read.say(text)
        if say is None:
            skipped = [*skipped, sentence]
            continue
        claim = nearest_claim(text, node["claims"])
        beats = [*beats, Beat(kind, text, say, claim["id"] if claim else None, claim["page_pdf"] if claim else None)]
        words += len(text.split())
    if len(beats) < MIN_BEATS or beats[0].kind != "main":
        return [], skipped
    title = read.say(node["short_title"])
    opening = [Beat("title", node["short_title"], title if title.endswith(("?", "!")) else f"{title}.")] if title else []
    return [*opening, *beats], skipped
