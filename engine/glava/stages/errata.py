"""Лист опечаток главы: модель сравнивает md со сканом страницы, код оставляет только проверяемые записи."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from glava.llm import Provider, Reply, ask_json
from glava.verify import quote_on_page

KINDS = ("recognition", "suspect")
FIELDS = ("md", "scan", "kind")
DPI = 150
Entry = Mapping[str, Any]


def render_page(pdf: Path, page: int, folder: Path) -> Path:
    import pymupdf

    target = folder / f"p{page:03d}.png"
    if not target.exists():
        folder.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(pdf) as document:
            document[page - 1].get_pixmap(dpi=DPI).save(target)
    return target


def _entry_issue(entry: Any, text: str) -> str | None:
    if not isinstance(entry, dict) or any(not str(entry.get(f) or "").strip() for f in FIELDS):
        return f"в записи нужны поля {FIELDS}"
    if entry["kind"] not in KINDS:
        return f"kind должен быть из {KINDS}"
    if not quote_on_page(entry["md"], text):
        return f"текста «{entry['md'][:60]}» нет на странице md дословно (нужно не меньше 8 знаков подряд)"
    if entry["md"].strip() == entry["scan"].strip():
        return f"«{entry['md'][:60]}»: scan совпадает с md"
    return None


def errata_issues(data: Any, text: str) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return ["нужен объект с массивом entries"]
    return [issue for e in data["entries"] if (issue := _entry_issue(e, text))]


def make_errata(provider: Provider, system: str, page: int, text: str, image: Path) -> tuple[list[dict], list[Reply]]:
    data, replies = ask_json(provider, system, f"# Страница {page}, текст md\n{text}", lambda d: errata_issues(d, text), attempts=2, files=(image,))
    entries = data.get("entries", []) if isinstance(data, dict) else []
    return [{**e, "page": page} for e in entries if _entry_issue(e, text) is None], replies


def for_pages(entries: Sequence[Entry], pages: Sequence[int]) -> list[Entry]:
    return [e for e in entries if e["page"] in pages]


def prompt_block(entries: Sequence[Entry]) -> str:
    if not entries:
        return ""
    rows = [f"- стр. {e['page']}: в md «{e['md']}» -> " + (f"в книге «{e['scan']}»" if e["kind"] == "recognition" else f"в книге так же, но вероятно «{e['scan']}»")
            + (f" ({e['note']})" if e.get("note") else "") for e in entries]
    return ("\n\n# Лист опечаток\nВ своих текстах, терминах и формулах пиши исправленное обозначение; в quote оставляй текст md дословно. Запись «вероятно» — "
            "возможная опечатка самого издания: приведи значение книги и скажи, что это, вероятно, опечатка, и какое значение правдоподобно.\n" + "\n".join(rows))


def number_sources(entries: Sequence[Entry]) -> dict[int, str]:
    found: dict[int, str] = {}
    for entry in entries:
        found = {**found, entry["page"]: f"{found.get(entry['page'], '')}\n{entry['scan']} {entry.get('note') or ''}"}
    return found
