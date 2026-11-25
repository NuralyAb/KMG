"""Карточка, состав главы и узел: сборка ответов из файлов конвейера."""

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

from glava.modules.catalog.repository import STAGES, ChapterInfo, Repository, iso
from glava.modules.catalog.schemas import (
    ChapterCard,
    ChapterDetail,
    Counts,
    Difficulty,
    NodeDetail,
    NodeRow,
    Part,
    Stage,
    Video,
)
from glava.modules.metrics.api import MetricRow, totals
from glava.shared.http.errors import not_found
from glava.shared.identifiers import is_safe_id, safe_parts
from glava.shared.json_store import rows

Row = Mapping[str, Any]
OTHER_PART = "Вне частей"


def build_stages(times: Mapping[str, float | None]) -> tuple[Stage, ...]:
    """Этап устарел, если его файл старше файла ближайшего предыдущего этапа, который уже есть."""
    stages: tuple[Stage, ...] = ()
    previous: float | None = None
    for name in STAGES:
        time = times[name]
        if time is None:
            stages = (*stages, Stage(name=name, state="missing", updated_at=None))
            continue
        is_stale = previous is not None and time < previous
        stages = (*stages, Stage(name=name, state="stale" if is_stale else "ready", updated_at=iso(time)))
        previous = time
    return stages


def course_url(chapter_id: str, path: str) -> str | None:
    """Адрес файла курса; None, если путь в данных небезопасен."""
    return f"/course/{chapter_id}/{quote(path)}" if safe_parts(path) else None


def is_covered(row: Row) -> bool:
    return bool(row.get("node_ids"))


def is_accounted(row: Row) -> bool:
    """Единица учтена: вошла в узел или это заголовок с названной причиной. Иное с причиной остаётся пропуском."""
    return is_covered(row) or (row.get("kind") == "heading" and bool(row.get("reason")))


def coverage_meta(coverage: Sequence[Row]) -> dict[str, int]:
    covered = sum(is_covered(r) for r in coverage)
    return {"total": len(coverage), "covered": covered, "skipped": len(coverage) - covered}


def errata_meta(entries: Sequence[Row]) -> dict[str, int]:
    kinds = Counter(e.get("kind") for e in entries)
    return {"recognition": kinds["recognition"], "suspect": kinds["suspect"]}


def build_card(repository: Repository, chapter: ChapterInfo, metrics: Sequence[MetricRow], active_run: str | None) -> ChapterCard:
    nodes, coverage = repository.nodes(chapter.id), repository.coverage(chapter.id)
    spent = totals([m for m in metrics if m.chapter == chapter.id])
    counts = Counts(
        nodes=len(nodes), claims=sum(len(rows(n.get("claims"))) for n in nodes), tasks=len(repository.tasks(chapter.id)),
        illustrations=len(repository.illustrations(chapter.id)), errata=len(repository.errata(chapter.id)), units=len(coverage),
        units_covered=sum(is_accounted(r) for r in coverage), videos=len(repository.passports(chapter.id)),
    )
    return ChapterCard(
        id=chapter.id, title=chapter.title, book=chapter.book, domain=chapter.domain, pages=chapter.pages, counts=counts,
        issues=repository.issue_count(chapter.id), stages=build_stages(repository.stage_times(chapter)), cost_usd=spent.cost_usd,
        tokens_in=spent.tokens_in, tokens_out=spent.tokens_out,
        course_url=course_url(chapter.id, "index.html") if repository.has_course(chapter.id) else None, active_run=active_run,
    )


def _order(node: Row) -> int:
    order = node.get("order")
    return order if isinstance(order, int) else 0


def _difficulty(value: Any) -> Difficulty:
    raw = value if isinstance(value, dict) else {}
    secondary = raw.get("secondary")
    return Difficulty(primary=str(raw.get("primary") or ""), secondary=str(secondary) if secondary else None)


def _node_row(node: Row, tasks: Mapping[str, int], formats: Mapping[str, str]) -> NodeRow:
    claims = rows(node.get("claims"))
    scans, pages = node.get("needs_scan"), node.get("pages")
    return NodeRow(
        id=node["id"], order=_order(node), title=str(node.get("title") or node["id"]), short_title=str(node.get("short_title") or node.get("title") or node["id"]),
        difficulty=_difficulty(node.get("difficulty")), threshold=node.get("threshold") is True,
        pages=tuple(p for p in pages if isinstance(p, int)) if isinstance(pages, list) else (), claims=len(claims), tasks=tasks.get(node["id"], 0),
        format=formats.get(node["id"]), needs_scan=sum(c.get("needs_scan") is True for c in claims) + (len(scans) if isinstance(scans, list) else 0),
    )


def build_detail(repository: Repository, chapter: ChapterInfo, metrics: Sequence[MetricRow], active_run: str | None) -> ChapterDetail:
    card = build_card(repository, chapter, metrics, active_run)
    tasks = Counter(str(t.get("step_id")) for t in repository.tasks(chapter.id))
    formats = {str(r.get("node_id")): r["format"] for r in repository.routes(chapter.id) if isinstance(r.get("format"), str)}
    ready = {n["id"]: _node_row(n, tasks, formats) for n in sorted(repository.nodes(chapter.id), key=_order)}
    listed = [(str(p.get("title") or ""), [ready[i] for i in p.get("nodes") or [] if isinstance(i, str) and i in ready])
              for p in repository.parts(chapter.id)]
    placed = {n.id for _, found in listed for n in found}
    rest = [n for n in ready.values() if n.id not in placed]
    # части, узлы которых ещё не собраны, не показываются
    parts = [(title, found) for title, found in [*listed, (OTHER_PART, rest)] if found]
    return ChapterDetail(**dict(card), parts=tuple(Part(title=title, nodes=tuple(found)) for title, found in parts))


def illustrations_with_url(repository: Repository, chapter_id: str) -> list[dict[str, Any]]:
    return [{**i, "url": course_url(chapter_id, str(i.get("file") or ""))} for i in repository.illustrations(chapter_id)]


def build_node(repository: Repository, chapter_id: str, node_id: str) -> NodeDetail:
    nodes = sorted(repository.nodes(chapter_id), key=_order)
    ids = [n["id"] for n in nodes]
    if not is_safe_id(node_id) or node_id not in ids:
        raise not_found("Такого узла в главе нет")
    place = ids.index(node_id)
    return NodeDetail(
        node=nodes[place], route=next((r for r in repository.routes(chapter_id) if r.get("node_id") == node_id), None),
        tasks=[t for t in repository.tasks(chapter_id) if t.get("step_id") == node_id],
        illustrations=[i for i in illustrations_with_url(repository, chapter_id) if node_id in (i.get("node_id"), i.get("step_id"))],
        prev=ids[place - 1] if place else None, next=ids[place + 1] if place + 1 < len(ids) else None,
    )


def filter_tasks(tasks: Sequence[dict[str, Any]], kind: str | None, node: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """by_type считается до отбора по типу, чтобы показать, сколько заданий в каждом."""
    of_node = [t for t in tasks if not node or t.get("step_id") == node]
    found = [t for t in of_node if not kind or t.get("type") == kind]
    return found, {"total": len(found), "by_type": dict(Counter(str(t.get("type")) for t in of_node))}


def _duration(value: Any) -> float:
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    return float(value) if is_number and math.isfinite(value) else 0.0


def _format(passport: Row, name: str) -> str:
    stated = passport.get("format")
    return stated if stated in ("9:16", "16:9") else ("16:9" if name.endswith("_wide") else "9:16")


def build_videos(repository: Repository, chapter_id: str) -> list[Video]:
    def video(name: str, passport: dict[str, Any]) -> Video:
        raw_audio, raw_card = passport.get("audio_check"), passport.get("node_card")
        audio, card = raw_audio if isinstance(raw_audio, dict) else {}, raw_card if isinstance(raw_card, dict) else {}
        problems = audio.get("problems")
        return Video(
            id=name, chapter=chapter_id, title=str(card.get("title") or name), format=_format(passport, name), duration_s=_duration(audio.get("duration_s")),
            url=f"/course/{chapter_id}/videos/{name}.mp4",
            subtitles_url=f"/course/{chapter_id}/videos/{name}.srt" if repository.has_subtitles(chapter_id, name) else None,
            passport=passport, problems=[str(p) for p in problems] if isinstance(problems, list) else [],
        )

    return [video(name, passport) for name, passport in repository.passports(chapter_id)]
