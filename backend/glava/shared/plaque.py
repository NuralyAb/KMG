"""Плашка на кадре ролика: если она говорит о масштабе, то с числом. Общее для проверки спецификации и отчёта ready."""

import re
from collections.abc import Sequence

# ТЗ требует назвать преувеличение числом («поры увеличены в 10 000 раз»), а не общей оговоркой
SCALE_WORDS = re.compile(r"увелич|уменьш|преувелич|растянут|сжат|шире|толще|выше|ниже|крупн|масштаб", re.IGNORECASE)


def plaque_errors(plaque: Sequence[str]) -> list[str]:
    vague = [p for p in plaque if SCALE_WORDS.search(p) and not re.search(r"\d", p)]
    return [f"плашка «{p}»: преувеличение назовите числом или уберите — масштаб подпишет шаблон" for p in vague]
