"""Машинная проверка слоя: цитата стоит на своей странице, числа есть в источнике, термин не раньше объяснения."""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

MIN_QUOTE_CHARS = 8
NUMBER = re.compile(r"(?<!\w)(?<!\d[.,])\d+(?:[.,]\d+)?")
DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‑": "-", "«": '"', "»": '"', "“": '"', "”": '"', "ё": "е"})


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


def find_quote_page(quote: str, pages: Mapping[int, str]) -> int | None:
    return next((n for n in sorted(pages) if quote_on_page(quote, pages[n])), None)


def numbers_in(text: str) -> set[str]:
    plain = text.translate(DASHES)
    found = (m.group().replace(",", ".") for m in NUMBER.finditer(plain.replace("-", " ")))
    return {n.rstrip("0").rstrip(".") if "." in n else (n.lstrip("0") or "0") for n in found}


def unsupported_numbers(text: str, source: str) -> set[str]:
    return numbers_in(text) - numbers_in(source)


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


def term_order_issues(nodes: Iterable[Mapping]) -> list[Issue]:
    """Ни один термин не используется раньше узла, где он объяснён."""
    ordered = sorted(nodes, key=lambda n: n["order"])
    home = {t.casefold(): n["order"] for n in reversed(ordered) for t in n["terms_introduced"]}
    return [
        Issue("term_before_definition", node["id"], f"термин «{term}» объяснён позже, в узле {home[term.casefold()]}")
        for node in ordered
        for term in node.get("terms_used", [])
        if home.get(term.casefold(), 0) > node["order"]
    ]


def with_extra(pages: Mapping[int, str], extra: Mapping[int, str]) -> dict[int, str]:
    return {n: f"{text}\n{extra.get(n, '')}" for n, text in pages.items()}


def verify_layer(layer: Mapping, pages: Mapping[int, str], extra: Mapping[int, str] | None = None) -> list[Issue]:
    """extra — исправления по скану: ими подтверждаются числа, но не цитаты."""
    nodes = layer["nodes"]
    numbers = with_extra(pages, extra or {})
    issues = [i for node in nodes for i in (*_quote_issues(node, pages), *_number_issues(node, numbers))]
    return [*issues, *term_order_issues(nodes)]
