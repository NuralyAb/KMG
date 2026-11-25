"""Модуль проверки: два независимых прохода ищут ошибки, судья отсеивает ложные тревоги, страницу ставит код."""

import json
import re
import shutil
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PureWindowsPath
from typing import Any

import jsonschema

from glava.modules.llm.api import Provider, Reply, ask_json
from glava.modules.review.checks import quick_notes
from glava.shared.evidence import find_quote_page, quote_on_page
from glava.shared.json_schemas import load_schema

SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
IMAGES = {".png", ".jpg", ".jpeg"}
GROUP = 8
FRAME_GROUP = 3
JUDGE_GROUP = 5
PARALLEL = 4
MIN_CONFIDENCE = 80
ORDER = {"critical": 0, "significant": 1, "minor": 2}
FIELDS = ("target", "category", "severity", "problem", "fix", "page_pdf", "quote")
Pages = Mapping[int, str]
Remark = Mapping[str, Any]
Item = Mapping[str, Any]


def load_package(source: Path) -> dict[str, Any]:
    """Чужой файл: сначала схема и пути, потом работа."""
    package = json.loads((source / "package.json").read_text(encoding="utf-8"))
    error = next(jsonschema.Draft202012Validator(load_schema("review_package")).iter_errors(package), None)
    if error:
        raise ValueError(f"пакет не по схеме: {'/'.join(map(str, error.absolute_path))}: {error.message[:200]}")
    if not SAFE_ID.fullmatch(package["package_id"]):
        raise ValueError("package_id: только буквы, цифры, точка, дефис и подчёркивание")
    root = source.resolve()
    for frame in package["frames"]:
        path = (root / frame["file"]).resolve()
        # адрес с диском не годится и там, где система его диском не считает
        if PureWindowsPath(frame["file"]).drive or not path.is_relative_to(root) or path.suffix.lower() not in IMAGES:
            raise ValueError(f"кадр {frame['id']}: недопустимый файл {frame['file']}")
    return package


def workspace(source: Path, root: Path, name: str) -> Path:
    """Рабочая копия пакета без ключа: модель с правом читать файлы не должна его увидеть. Копируются только картинки."""
    target = (root / name).resolve()
    if not name or target.parent != root.resolve():
        raise ValueError(f"недопустимое имя рабочей папки: {name!r}")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    shutil.copy2(source / "package.json", target / "package.json")
    for image in source.rglob("*"):
        if image.is_file() and not image.is_symlink() and image.suffix.lower() in IMAGES:
            place = target / image.relative_to(source)
            place.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, place)
    return target


def _claim_page(item: Item, package: Mapping[str, Any]) -> int | None:
    by_id = {i["id"]: i for i in package["items"]}
    if item.get("page_pdf"):
        return item["page_pdf"]
    if item.get("claim_ref") in by_id:
        return by_id[item["claim_ref"]].get("page_pdf")
    nodes = {item.get("node_id")} - {None} or {s["spec"].get("node_id") for s in package["scenes"] if s["video_id"] == item.get("video_id")}
    return next((i["page_pdf"] for i in package["items"] if i.get("node_id") in nodes and i.get("page_pdf")), None)


def evidence_pages(items: Sequence[Item], package: Mapping[str, Any], pages: Pages) -> list[int]:
    found = {p for i in items if (p := _claim_page(i, package))}
    if not found:
        return sorted(pages)
    return sorted({n for p in found for n in (p - 1, p, p + 1) if n in pages})


def settle_page(remark: Remark, pages: Pages, fallback: int | None) -> int | None:
    """Страница — там, где стоит цитата; без цитаты верим странице утверждения."""
    quote, page = remark.get("quote") or "", remark.get("page_pdf")
    if page in pages and quote_on_page(quote, pages[page]):
        return page
    real = find_quote_page(quote, pages) if quote else None
    return real or fallback or (page if page in pages else None)


def _listed(items: Sequence[Item], package: Mapping[str, Any], pages: Pages) -> str:
    by_id = {i["id"]: i for i in package["items"]}
    rows = []
    for item in items:
        extra = {"опирается_на": by_id[item["claim_ref"]]["text"]} if item.get("claim_ref") in by_id else {}
        notes = [] if item["type"] == "frame" else quick_notes(item, pages)
        rows = [*rows, {k: v for k, v in {**item, **extra, "заметки_кода": notes}.items() if v}]
    return json.dumps(rows, ensure_ascii=False, indent=0)


def _context(items: Sequence[Item], package: Mapping[str, Any], pages: Pages, checklist: str) -> str:
    text = "\n\n".join(f"=== стр. {n} ===\n{pages[n]}" for n in evidence_pages(items, package, pages))
    videos = {i["video_id"] for i in items if i.get("video_id")}
    specs = [s for s in package["scenes"] if s["video_id"] in videos]
    scenes = f"\n\n# Спецификации сцен\n{json.dumps(specs, ensure_ascii=False)}" if specs else ""
    return f"# Глава\n{text}{scenes}\n\n# Чек-лист\n{checklist}\n\n# Элементы\n{_listed(items, package, pages)}"


def _images(items: Sequence[Item], folder: Path | None) -> tuple[Path, ...]:
    return tuple(folder / i["file"] for i in items if i.get("file")) if folder else ()


def _shape_issues(data: Any, key: str) -> list[str]:
    return [] if isinstance(data, dict) and isinstance(data.get(key), list) else [f"нужен объект с массивом {key}"]


def _ask(provider: Provider, system: str, prompt: str, items: Sequence[Item], folder: Path | None, key: str) -> tuple[list[dict], list[Reply]]:
    data, replies = ask_json(provider, system, prompt, lambda d: _shape_issues(d, key), files=_images(items, folder))
    ids = {i["id"] for i in items}
    return [r for r in data[key] if isinstance(r, dict) and r.get("target") in ids], replies


def _batches(values: Sequence[Any], size: int) -> list[Sequence[Any]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def _valid(remark: Remark) -> bool:
    schema = load_schema("review_output")["properties"]["remarks"]["items"]["properties"]
    return (remark.get("category") in schema["category"]["enum"] and remark.get("severity") in schema["severity"]["enum"]
            and bool(str(remark.get("problem") or "").strip()) and bool(str(remark.get("fix") or "").strip()))


def _confidence(verdict: Remark) -> float:
    try:
        return float(verdict.get("confidence", 0))
    except (TypeError, ValueError):
        return 0.0


def _group_by_target(remarks: Sequence[Remark]) -> dict[str, list[Remark]]:
    grouped: dict[str, list[Remark]] = {}
    for remark in remarks:
        grouped = {**grouped, remark["target"]: [*grouped.get(remark["target"], []), remark]}
    return grouped


def review_package(
    package: Mapping[str, Any], pages: Pages, provider: Provider, prompts: Mapping[str, str], checklist: str,
    folder: Path | None = None, min_confidence: int = MIN_CONFIDENCE, judge: Provider | None = None,
) -> tuple[dict[str, Any], list[Reply]]:
    items = [*package["items"], *({**f, "type": "frame"} for f in package["frames"])]
    by_id = {i["id"]: i for i in items}

    def place(target: str) -> tuple[int, str]:
        return _claim_page(by_id[target], package) or 0, target

    texts = [by_id[t] for t in sorted((i["id"] for i in package["items"]), key=place)]
    batches = [*_batches(texts, GROUP), *_batches([i for i in items if i["type"] == "frame"], FRAME_GROUP)]

    def find(job: tuple[str, Sequence[Item]]) -> tuple[list[dict], list[Reply]]:
        role, batch = job
        return _ask(provider, prompts[role], _context(batch, package, pages, checklist), batch, folder, "remarks")

    def decide(batch: Sequence[tuple[str, Sequence[Remark]]]) -> tuple[list[dict], list[Reply]]:
        chosen = [by_id[t] for t, _ in batch]
        doubts = json.dumps([{"target": t, "замечания": list(rs)} for t, rs in batch], ensure_ascii=False, indent=0)
        prompt = f"{_context(chosen, package, pages, checklist)}\n\n# Замечания проверяющих\n{doubts}"
        return _ask(judge or provider, prompts["judge"], prompt, chosen, folder, "verdicts")

    with ThreadPoolExecutor(PARALLEL) as pool:
        found = list(pool.map(find, [(role, batch) for role in ("find", "physics") for batch in batches]))
        doubts = _group_by_target([r for rs, _ in found for r in rs])
        verdicts = list(pool.map(decide, _batches([(t, doubts[t]) for t in sorted(doubts, key=place)], JUDGE_GROUP)))
    final: dict[str, dict] = {}
    for verdict in (v for vs, _ in verdicts for v in vs):
        sure = verdict.get("confirmed") is True and _confidence(verdict) >= min_confidence
        if sure and _valid(verdict) and verdict["target"] not in final:
            page = settle_page(verdict, pages, _claim_page(by_id[verdict["target"]], package))
            quote = verdict.get("quote")
            quote = quote if isinstance(quote, str) and find_quote_page(quote, pages) else None
            final = {**final, verdict["target"]: {**{k: verdict.get(k) for k in FIELDS}, "page_pdf": page, "quote": quote}}
    remarks = sorted(final.values(), key=lambda r: (ORDER[r["severity"]], r["target"]))
    return {"package_id": package["package_id"], "remarks": remarks}, [r for _, rs in (*found, *verdicts) for r in rs]
