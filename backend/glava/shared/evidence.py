"""Машинная проверка слоя: цитата стоит на своей странице, числа есть в источнике, термин не раньше объяснения."""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache

from glava.shared.english import SPACED, exact_quote, plain_numbers
from glava.shared.language import has_english

MIN_QUOTE_CHARS = 8
NUMBER = re.compile(r"(?<!\w)(?<!\d[.,])\d+(?:[.,]\d+)?")
DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‑": "-", "«": '"', "»": '"', "“": '"', "”": '"', "ё": "е"})

ORIGINAL = re.compile(r"\s*\([A-Za-z][A-Za-z\d\s,;/'’-]*[a-z][A-Za-z\d\s,;/'’-]*\)")


@dataclass(frozen=True)
class Issue:
    code: str
    where: str
    message: str


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def quote_on_page(quote: str, page: str) -> bool:
    """Цитата дословна; не учитываются только пробелы, переносы строк и регистр."""
    needle = squeeze(quote)
    return len(needle) >= MIN_QUOTE_CHARS and needle in squeeze(page)


DISPLAY = re.compile(r"\$\$[\s\S]+?\$\$")


def whole_formula(quote: str, text: str) -> str:
    """Цитата, оборванная внутри выключной формулы $$…$$, дополняется до целой формулы из того же текста.
    Курс не может нарисовать половину формулы, а цитата остаётся дословной: добавляется только недостающий кусок страницы."""
    if quote.count("$$") % 2 == 0 and not ("$" not in quote and "\\" in quote):
        return quote
    for block in DISPLAY.findall(text):
        inner = squeeze(block[2:-2])
        parts = quote.split("$$")
        if len(parts) == 2 and parts[1].strip() and squeeze(parts[1]) and inner.startswith(squeeze(parts[1])):
            return f"{parts[0]}{block}"  # оборван конец формулы
        if len(parts) == 2 and parts[0].strip() and squeeze(parts[0]) and inner.endswith(squeeze(parts[0])):
            return f"{block}{parts[1]}"  # оборвано начало формулы
        if len(parts) == 1 and squeeze(quote) in inner:
            return block  # кусок из середины формулы без знаков доллара
    return quote


def find_quote_page(quote: str, pages: Mapping[int, str]) -> int | None:
    return next((n for n in sorted(pages) if quote_on_page(quote, pages[n])), None)


def restored_quote(quote: str, text: str) -> str | None:
    """Английская цитата с прямыми кавычками или без переноса, в точности как на странице. Слова и числа не правятся."""
    found = exact_quote(quote, text) if has_english(text) else None
    return found if found and quote_on_page(found, text) else None


def numbers_in(text: str) -> set[str]:
    plain = text.translate(DASHES)
    found = (m.group().replace(",", ".") for m in NUMBER.finditer(plain.replace("-", " ")))
    return {n.rstrip("0").rstrip(".") if "." in n else (n.lstrip("0") or "0") for n in found}


@lru_cache(maxsize=512)
def _english_numbers(source: str) -> frozenset[str]:
    return frozenset().union(*(numbers_in(t) for t in plain_numbers(source)))


def unsupported_numbers(text: str, source: str) -> set[str]:
    if not has_english(source):
        return numbers_in(text) - numbers_in(source)
    # в английском источнике 1,000 — тысяча; в русском тексте её пишут и слитно, и с пробелом
    allowed = _english_numbers(source)
    return min((numbers_in(t) - allowed for t in (text, SPACED.sub("", text))), key=len)


SERVICE_KEYS = {"quote", "id", "ref", "unit_id", "page_pdf", "page_print", "target", "number"}
TEXT_FIELDS = ("layers", "misconception", "data_meaning", "it_analogy", "now_practice", "inefficiency_lens", "decision_on_data", "glossary", "worked_examples",
               "book_tasks")


def _strings(value: object, where: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, Mapping):
        for key, inner in value.items():
            if key not in SERVICE_KEYS:
                yield from _strings(inner, f"{where}.{key}")
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            yield from _strings(inner, f"{where}[{i}]")


def node_texts(node: Mapping) -> Iterator[tuple[str, str]]:
    """Все тексты узла, которые увидит читатель: в них не может быть чисел, которых нет на страницах узла."""
    for field in TEXT_FIELDS:
        yield from _strings(node.get(field), field)
    for claim in node["claims"]:
        yield claim["id"], claim["text"]


def node_source(node: Mapping, pages: Mapping[int, str]) -> str:
    cited = {c["page_pdf"] for c in node["claims"]} | set(node.get("pages", []))
    cited |= {e["page_pdf"] for key in ("worked_examples", "book_tasks") for e in node.get(key) or []}
    return "\n".join(pages.get(n, "") for n in sorted(cited))


def _quote_issues(node: Mapping, pages: Mapping[int, str]) -> Iterator[Issue]:
    for claim in node["claims"]:
        if quote_on_page(claim["quote"], pages.get(claim["page_pdf"], "")):
            continue
        real = find_quote_page(claim["quote"], pages)
        if real is None:
            yield Issue("quote_not_found", claim["id"], f"цитаты нет в главе: {claim['quote'][:80]}")
        else:
            yield Issue("quote_wrong_page", claim["id"], f"цитата на стр. {real}, указана {claim['page_pdf']}")


def _number_issues(node: Mapping, pages: Mapping[int, str]) -> Iterator[Issue]:
    source = node_source(node, pages)
    for where, text in node_texts(node):
        missing = unsupported_numbers(text, source)
        if missing:
            yield Issue("number_not_in_source", f"{node['id']}:{where}", f"чисел нет на страницах узла: {', '.join(sorted(missing))}")


def bare_term(term: str) -> str:
    """Термин без английского оригинала в скобках: «пористость (porosity)» и «пористость» — одно и то же."""
    return ORIGINAL.sub("", term).strip().casefold() or term.casefold()


def term_order_issues(nodes: Iterable[Mapping]) -> list[Issue]:
    """Ни один термин не используется раньше узла, где он объяснён."""
    ordered = sorted(nodes, key=lambda n: n["order"])
    home = {bare_term(t): n["order"] for n in reversed(ordered) for t in n["terms_introduced"]}
    return [
        Issue("term_before_definition", node["id"], f"термин «{term}» объяснён позже, в узле {home[bare_term(term)]}")
        for node in ordered
        for term in node.get("terms_used", [])
        if home.get(bare_term(term), 0) > node["order"]
    ]


def with_extra(pages: Mapping[int, str], extra: Mapping[int, str]) -> dict[int, str]:
    return {n: f"{text}\n{extra.get(n, '')}" for n, text in pages.items()}


def verify_layer(layer: Mapping, pages: Mapping[int, str], extra: Mapping[int, str] | None = None) -> list[Issue]:
    """extra — исправления по скану: ими подтверждаются числа, но не цитаты."""
    nodes = layer["nodes"]
    numbers = with_extra(pages, extra or {})
    issues = [i for node in nodes for i in (*_quote_issues(node, pages), *_number_issues(node, numbers))]
    return [*issues, *term_order_issues(nodes)]
