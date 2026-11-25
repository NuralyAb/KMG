"""Сверка русского утверждения с английской цитатой: отрицания, направления, кванторы, оговорки, единицы по словарям двух языков.

Слова двух языков не совпадают по счёту, поэтому сравнивается наличие, а не число. Находка — повод посмотреть, а не приговор.
"""

import re

from glava.shared.evidence import DASHES


def _any(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


SAID_NOT = _any(r"\b(?:не|нет|ни|без|нельзя|невозможно|никогда|никак\w*)\b|\bотсутств\w*|\bне(?:зависим|измен|возможн|льзя|достат)\w*")
# «не более», «не только» отрицанием не считаются
SAID_DOUBLE = _any(r"\bне\s+(?:только|менее|более|больше|меньше|ниже|выше)\b")
HEARD_NOT = _any(r"\b(?:not|no|nor|neither|never|none|without|cannot|impossible|absen(?:t|ce)|lacks?|lacking|fails?|unable|hardly)\b|n['’]t\b")
HEARD_DOUBLE = _any(r"\b(?:not only|no (?:more|less|greater|fewer|later) than|not (?:more|less) than|no matter)\b")
# эти слова законно переводятся с «не», но пропуск «не» при них ошибкой не считается
SOFT_NOT = _any(r"\b(?:un\w{3,}|in(?:dependent|sensitive|soluble|compressible|sufficient|significant|adequate|accurate|complete|active|variable|finite)\w*|im(?:permeable|possible|movable|mobile|miscible|perfect)\w*|"
                r"non\w{2,}|constant\w*|independent\w*|neglect\w*|negligible|ignor\w*|rather than|instead of|except|little|few|avoid\w*|prevent\w*|regardless|exclud\w*|free of|\w+less|dis\w{4,}|ir\w{4,}|only)\b")

SAID_ALL = _any(r"\b(?:всегда|никогда|вс[её]|все|всех|всеми|люб(?:ой|ая|ое|ые|ого|ых|ым|ую|ом)|только|лишь|исключительно|кажд\w+|обязательно|полностью)\b")
HEARD_ALL = _any(r"\b(?:always|never|all|any|every|each|only|solely|exclusively|entire\w*|complete\w*|whole|full|fully|must|necessarily|total\w*|throughout|both|just|none|no)\b|\bunless\b")

HEARD_HEDGE = _any(
    r"\b(?:usually|often|sometimes|seldom|rarely|mainly|mostly|approximately|roughly|nearly|almost|possibly|probably|perhaps|presumably|may|might|generally|typically|commonly|frequently|"
    r"normally|primarily|largely|practically|likely|tends?|in general|in most|in some|in certain|on average|under certain|as a rule|to some extent)\b|"
    r"\b(?:about|around|some|order of)\s+[~$]?\d")
HEARD_IF = _any(r"\b(?:if|provided|unless|except)\b")
SAID_HEDGE = _any(
    r"\b(?:обычно|часто|иногда|редко|нередко|преимущественно|примерно|приблизительно|около|порядка|почти|возможн\w+|вероятн\w+|мож(?:ет|но)|могут|если|при условии|"
    r"как правило|в основном|главным образом|в большинстве|в некоторых|в отдельных|в ряде|в общем|в среднем|чаще|кроме|за исключением|условно|практически|по-видимому|склон\w+|стрем\w+|"
    r"как будто|предположительно|типичн\w+|обыкновенно|до некоторой степени|зачастую|в целом|порой|нормальн\w+)\b")
# условие по-русски часто стоит без «если»: «при росте давления», «без притока», «только в песках»
SAID_IF = _any(r"\b(?:при|когда|в случае|без|лишь|только|пока)\b")

# слева рост и больше, справа падение и меньше: перевод свободно меняет «higher» на «растёт», поэтому пары объединены
DIRECTIONS = (
    ((_any(r"\b(?:увелич|возраст|повыш|раст[её]т|растут|рост|наращ|превыша)\w*|\b(?:больш(?:е|ий|ая|ое|ие|их|им|ими|ей|ую)|выше|высок\w+|максим\w+)\b|[>≥]|\\geq?\b"),
      _any(r"\b(?:уменьш|сниж|пониж|убыва|сокращ|пада[ею])\w*|\b(?:меньш(?:е|ий|ая|ое|ие|их|им|ими|ей|ую)|ниже|низк\w+|миним\w+)\b|[<≤]|\\leq?\b")),
     (_any(r"\b(?:increas|ris(?:e|es|ing)|grow|rais|exceed|enlarg|build-?up)\w*|\b(?:rose|higher|high|highest|greater|greatest|larger|largest|above|more|maxim\w+)\b|[>≥]|\\geq?\b"),
      _any(r"\b(?:decreas|declin|reduc|diminish|lower|drop|fall|lessen)\w*|\b(?:fell|low|less|smaller|smallest|below|fewer|minim\w+)\b|[<≤]|\\leq?\b"))),
    ((_any(r"\b(?:положительн\w*|прям(?:ая|ой|о)\s)"), _any(r"\b(?:отрицательн\w*|обратн(?:ая|ой|о)\s)")),
     (_any(r"\b(?:positive\w*|direct(?:ly)? proportional)"), _any(r"\b(?:negative\w*|inverse\w*)"))),
)

# русское название единицы -> английские; единицы книги в слое не пересчитываются
UNITS = {
    "%": r"%|percent|per cent", "‰": r"‰", "°C": r"°\s?C|deg(?:rees?)? C", "°F": r"°\s?F|deg(?:rees?)? F", "МПа": r"MPa", "кПа": r"kPa", "Па": r"Pa", "атм": r"atm", "psi": r"psi[agi]?|lb/in\.?2?",
    "Ом·м": r"ohm[-·\s]?m(?:eters?)?|Ω[-·\s]?m", "мкм": r"µm|μm|microns?|micrometers?", "мм": r"mm", "см": r"cm", "км": r"km", "м": r"m|met(?:er|re)s?", "мД": r"m[dD]|millidarc(?:y|ies)", "Д": r"darc(?:y|ies)",
    "фут": r"ft|feet|foot", "дюйм": r"in\.|inch(?:es)?", "баррель": r"bbl|barrels?|STB|RB", "фунт": r"lbm?f?|pounds?", "галлон": r"gal(?:lons?)?", "миля": r"miles?", "г": r"g|grams?", "кг": r"kg", "т": r"tons?|tonnes?|t",
    "мин": r"min(?:utes?)?", "сут": r"days?|D|d", "ч": r"hours?|hrs?|h", "с": r"s|sec(?:onds?)?", "К": r"K",
}
SAID = {
    "%": r"%|процент\w*", "psi": r"psi[agi]?|фунт\w* на (?:квадратный )?дюйм\w*", "Ом·м": r"Ом[·*\s-]?м", "мД": r"мД|миллидарси", "Д": r"Д|дарси", "фут": r"фут\w*|ft", "дюйм": r"дюйм\w*", "баррель": r"барр(?:ел\w*)?\.?|bbl",
    "фунт": r"фунт\w*", "галлон": r"галлон\w*", "миля": r"мил[ьяией]\w*", "м": r"м|метр\w*", "км": r"км|километр\w*", "см": r"см|сантиметр\w*", "мм": r"мм|миллиметр\w*", "мкм": r"мкм|микрон\w*|микрометр\w*", "г": r"г|грамм\w*", "кг": r"кг|килограмм\w*",
    "т": r"т|тонн\w*", "мин": r"мин|минут\w*", "сут": r"сут\w*|дн(?:я|ей|ях)|день", "ч": r"ч|час\w*", "с": r"с|секунд\w*",
}
TAIL = r"(?:[²³]|\^\{?\d\}?)?(?![\w·])"
AMOUNT = r"\d(?:[\d.,]*\d)?[\s\u00a0-]*"


def _measured(text: str, names: dict[str, str]) -> set[str]:
    plain = text.translate(DASHES)
    return {unit for unit, pattern in names.items() if re.search(rf"{AMOUNT}(?:{pattern}){TAIL}", plain)}


SAID_UNITS = {unit: SAID.get(unit, re.escape(unit)) for unit in UNITS}


def is_hedged(quote: str) -> bool:
    return bool(HEARD_HEDGE.search(quote) or HEARD_IF.search(quote))


def _condition(text: str, quote: str) -> bool:
    if SAID_HEDGE.search(text):
        return False
    return bool(HEARD_HEDGE.search(quote)) or bool(HEARD_IF.search(quote) and not SAID_IF.search(text))


def _negation(text: str, quote: str) -> bool:
    said = bool(SAID_NOT.search(SAID_DOUBLE.sub(" ", text)))
    heard = bool(HEARD_NOT.search(HEARD_DOUBLE.sub(" ", quote)))
    return said != heard and not (said and SOFT_NOT.search(quote))


def _direction(text: str, quote: str) -> bool:
    for (said_up, said_down), (heard_up, heard_down) in DIRECTIONS:
        up, down, was_up, was_down = (len(p.findall(t)) for p, t in ((said_up, text), (said_down, text), (heard_up, quote), (heard_down, quote)))
        if (up < was_up and down > was_down) or (up > was_up and down < was_down):
            return True
    return False


def _unit(text: str, quote: str) -> bool:
    """Единица утверждения, которой нет в цитате. Если в цитате единиц при числах нет, сверять не с чем: она могла остаться в шапке таблицы."""
    heard = _measured(quote, UNITS)
    return bool(heard) and bool(_measured(text, SAID_UNITS) - heard)


def english_flags(text: str, quote: str) -> list[str]:
    """Коды расхождений русского утверждения с английской цитатой, кроме чисел."""
    found = (
        ("unit", _unit(text, quote)), ("negation", _negation(text, quote)), ("direction", _direction(text, quote)),
        ("quantifier", bool(SAID_ALL.search(text)) and not HEARD_ALL.search(quote)), ("condition", _condition(text, quote)),
    )
    return [code for code, is_found in found if is_found]
