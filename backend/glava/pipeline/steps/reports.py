"""templates, ready, process: отчёты для сдачи. Модель и книга не нужны."""

import ast
import csv
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from glava.modules.metrics.api import read_metrics
from glava.pipeline.steps.course import course_videos
from glava.shared.evidence import term_order_issues
from glava.shared.json_files import read, read_or, save
from glava.shared.json_schemas import load_schema
from glava.shared.plaque import plaque_errors
from glava.shared.paths import REPOSITORY, workspace

log = logging.getLogger("glava")
VIDEO_FORMATS = ("шортс", "длинное видео")
VIDEO_SCORE = 5
MIN_FITS = 2
MIN_TASKS, MIN_TYPES, MAX_COURSE_MB = 15, 4, 30
HOOK_SHARE = 0.2
VIDEO_FORMATS_NEEDED = {"9:16", "16:9"}


# ---------- покрытие шаблонами


@dataclass(frozen=True)
class VideoTemplate:
    name: str
    model: str
    fits: tuple[str, ...]


def video_templates(domain: Path) -> list[VideoTemplate]:
    """Шаблоны сцен читаются без запуска: pycairo для отчёта не нужен."""
    found: list[VideoTemplate] = []
    for file in sorted((domain / "video").glob("*.py")):
        names = {t.id: n.value for n in ast.parse(file.read_text(encoding="utf-8")).body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        summary = ast.literal_eval(names["SUMMARY"]) if "SUMMARY" in names else ""
        state = ast.literal_eval(names["STATE_MODEL"]) if "STATE_MODEL" in names else summary.split(".")[0]
        found = [*found, VideoTemplate(file.stem, state, tuple(ast.literal_eval(names["FITS"])) if "FITS" in names else ())]
    return found


def _node_text(node: Mapping[str, Any]) -> str:
    return " ".join([node["title"], node["layers"]["main"]["text"], *(c["text"] for c in node["claims"])]).casefold()


def template_for(node: Mapping[str, Any], route: Mapping[str, Any], templates: Sequence[VideoTemplate]) -> tuple[VideoTemplate | None, str]:
    named = next((t for t in templates if t.name == route.get("template")), None)
    if named:
        return named, "назначен маршрутизацией"
    text = _node_text(node)
    best = max(((sum(bool(re.search(p, text)) for p in t.fits), t) for t in templates), key=lambda x: x[0], default=(0, None))
    return (best[1], f"совпало признаков: {best[0]}, подтвердить человеку") if best[0] >= MIN_FITS else (None, "нужен новый")


def template_coverage(layer: Mapping[str, Any], routes: Sequence[Mapping[str, Any]], templates: Sequence[VideoTemplate]) -> list[dict[str, Any]]:
    nodes = {n["id"]: n for n in layer["nodes"]}
    rows: list[dict[str, Any]] = []
    for route in routes:
        score = sum(route["video_scores"].values())
        if route["node_id"] not in nodes or (route["format"] not in VIDEO_FORMATS and score < VIDEO_SCORE):
            continue
        template, why = template_for(nodes[route["node_id"]], route, templates)
        rows = [*rows, {"node_id": route["node_id"], "title": nodes[route["node_id"]]["title"], "format": route["format"], "video_score": score,
                        "template": template.name if template else None, "state_model": template.model if template else None, "status": why}]
    return rows


def build_templates(chapter_id: str) -> list[dict[str, Any]]:
    work = workspace() / "work" / chapter_id
    registry = read(workspace() / "chapters.json")["chapters"].get(chapter_id) or {}
    domain = workspace() / "domain" / registry.get("domain", "general")
    rows = template_coverage(read(work / "layer.json"), read(work / "routing.json")["routes"], video_templates(domain))
    save(work / "template_coverage.json", {"chapter": chapter_id, "domain": domain.name, "rows": rows})
    for row in rows:
        log.info("%s [%s, видеоёмкость %s]: %s (%s)", row["node_id"], row["format"], row["video_score"], row["template"] or "нужен новый", row["status"])
    log.info("видеоёмких узлов %s, с шаблоном %s", len(rows), sum(bool(r["template"]) for r in rows))
    return rows


# ---------- проверка сдачи


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _layer_checks(work: Path, layer: Mapping[str, Any]) -> list[Check]:
    nodes = layer["nodes"]
    claims = [c for n in nodes for c in n["claims"]]
    bare = [c["id"] for c in claims if not c.get("quote") or not c.get("page_pdf")]
    rows = read_or(work / "coverage.json", {"rows": []})["rows"]
    open_units = [r["unit_id"] for r in rows if not r["node_ids"] and not r["reason"]]
    early = term_order_issues(nodes)
    audit = read_or(work / "audit.json", {})
    return [
        Check("единицы главы покрыты", bool(rows) and not open_units, f"единиц {len(rows)}, без узла и причины {len(open_units)}"),
        Check("у утверждения цитата и страница", bool(claims) and not bare, f"утверждений {len(claims)}, без цитаты или страницы {len(bare)}"),
        Check("термин не раньше объяснения", not early, f"нарушений {len(early)}"),
        Check("слой сверен кодом (audit)", bool(audit), "есть audit.json" if audit else "выполните audit"),
        Check("узел «решение на данных»", any(n.get("decision_on_data") for n in nodes), f"узлов {sum(bool(n.get('decision_on_data')) for n in nodes)}"),
    ]


def _course_checks(work: Path, out: Path, layer: Mapping[str, Any]) -> list[Check]:
    tasks = read_or(work / "tasks.json", {"tasks": []})["tasks"]
    pictures = read_or(work / "illustrations.json", {"illustrations": []})["illustrations"]
    types = {t["type"] for t in tasks}
    drawn, exact = {p["step_id"] for p in pictures}, {p["step_id"] for p in pictures if p["frame_class"] in ("A", "B")}
    bare = [n["id"] for n in layer["nodes"] if n["id"] not in drawn]
    weak = [p["title"] for p in layer["parts"] if not exact & set(p["nodes"])]
    files = [f for f in out.rglob("*") if f.is_file() and f.suffix != ".mp4"] if out.exists() else []
    size = sum(f.stat().st_size for f in files) / 1e6
    return [
        Check("курс собран", (out / "index.html").exists(), str(out / "index.html")),
        Check("заданий не меньше 15", len(tasks) >= MIN_TASKS, f"заданий {len(tasks)}"),
        Check("типов заданий не меньше 4", len(types) >= MIN_TYPES, ", ".join(sorted(types))),
        Check("рисунок на каждом шаге", not bare, f"без рисунка {len(bare)}"),
        Check("рисунок A или B в каждой части", not weak, "; ".join(weak) or "есть"),
        Check("курс без видео до 30 МБ", size <= MAX_COURSE_MB, f"{size:.1f} МБ"),
    ]


def _route_checks(work: Path, layer: Mapping[str, Any], filmed: set[str]) -> list[Check]:
    routes = read_or(work / "routing.json", {"routes": []})["routes"]
    videos = [r for r in routes if r["format"] in VIDEO_FORMATS]
    hooks = sum(bool(r.get("hook_short")) for r in videos)
    live = set(read_or(work / "simulations.json", {"steps": {}})["steps"])
    open_nodes = [r["node_id"] for r in videos if r["node_id"] not in filmed | live]
    return [
        Check("маршрут у каждого узла", {r["node_id"] for r in routes} == {n["id"] for n in layer["nodes"]}, f"маршрутов {len(routes)}, узлов {len(layer['nodes'])}"),
        Check("крючков не больше 20 % роликов", not videos or hooks / len(videos) <= HOOK_SHARE, f"{hooks} из {len(videos)}"),
        Check("видеоузлы закрыты роликом или интерактивом", not open_nodes, ", ".join(open_nodes) or "закрыты"),
        Check("отчёт о покрытии шаблонами", (work / "template_coverage.json").exists(), "выполните templates" if not (work / "template_coverage.json").exists() else "есть"),
    ]


def _late_hook(passport: Mapping[str, Any]) -> list[str]:
    """Крючок по паспорту: ролики, снятые до проверки времени крючка, тоже проверяются. Время — по доле слов первой фразы."""
    script = passport.get("script") or []
    if not script:
        return []
    first = script[0]
    opening = re.split(r"(?<=[.!?])\s+", first["text"].strip())[0]
    end = first["t_start"] + (first["t_end"] - first["t_start"]) * len(opening.split()) / max(1, len(first["text"].split()))
    return [f"крючок дозвучал на {end:.1f} с, нужно до 3 с"] if end > 3.0 else []


def _passport_checks(out: Path) -> list[Check]:
    checks: list[Check] = []
    for file in sorted((out / "videos").glob("*.passport.json")):
        passport = read(file)
        name = file.name.removesuffix(".passport.json")
        wrong = [e.message[:100] for e in jsonschema.Draft202012Validator(load_schema("passport")).iter_errors(passport)]
        missing = [s for s in (".mp4", ".srt", ".scene.json") if not (file.parent / f"{name}{s}").exists()]
        problems = passport["audio_check"].get("problems", [])
        problems = [*problems, *(h for h in _late_hook(passport) if h not in problems)]
        scene = read_or(file.parent / f"{name}.scene.json", {})
        problems = [*problems, *plaque_errors(scene.get("plaque") or [])]
        bad_physics = [p["item"] for p in passport["physics_checklist"] if p["answer"] == "нет"]
        faults = [*wrong, *(f"нет файла {m}" for m in missing), *problems, *bad_physics]
        checks = [*checks, Check(f"ролик {name}", not faults, "; ".join(faults) or f"{passport['format']}, {passport['audio_check']['duration_s']} с, голос {passport['audio_check'].get('voice')}")]
    return checks


def chapter_checks(chapter_id: str) -> list[Check]:
    work, out = workspace() / "work" / chapter_id, workspace() / "out" / chapter_id
    if not (work / "layer.json").exists():
        return [Check("учебный слой", False, "слой не собран: build")]
    layer = read(work / "layer.json")
    filmed = set(course_videos(chapter_id))
    return [*_layer_checks(work, layer), *_route_checks(work, layer, filmed), *_course_checks(work, out, layer), *_passport_checks(out)]


def series_checks(passports: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[Check]:
    """Требования ко всей серии: два формата на разных главах и один голос."""
    by_format = {f: {c for c, ps in passports.items() for p in ps if p["format"] == f} for f in VIDEO_FORMATS_NEEDED}
    two = any(a != b for a in by_format["9:16"] for b in by_format["16:9"])
    voices = {(p["audio_check"].get("voice"), p["audio_check"].get("rate")) for ps in passports.values() for p in ps}
    found = ", ".join(f"{f}: {len(c)}" for f, c in sorted(by_format.items()))
    return [Check("шортс и разбор на двух разных главах", two, found),
            Check("один голос и темп на всю серию", len(voices) <= 1, "; ".join(f"{v} {r}" for v, r in sorted(voices, key=str)) or "роликов нет")]


def build_ready(chapter_ids: Sequence[str]) -> bool:
    """Чего не хватает по ТЗ: по каждой главе и по серии роликов."""
    report: dict[str, list[Check]] = {c: chapter_checks(c) for c in chapter_ids}
    passports = {c: [read(p) for p in sorted((workspace() / "out" / c / "videos").glob("*.passport.json"))] for c in chapter_ids}
    report = {**report, "серия роликов": series_checks(passports)}
    for title, checks in report.items():
        log.info("\n%s", title)
        for c in checks:
            log.info("  %s %s — %s", "да " if c.ok else "НЕТ", c.name, c.detail)
    missing = sum(not c.ok for checks in report.values() for c in checks)
    log.info("\nне хватает: %s", missing)
    return missing == 0


# ---------- процесс


def _edits() -> list[dict[str, str]]:
    path = REPOSITORY / "manual_edits.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _minutes(row: Mapping[str, str]) -> float:
    try:
        return float(row.get("person_minutes") or 0)
    except ValueError:
        return 0.0


def process_rows(chapter_ids: Sequence[str], usd_per_1k_chars: float = 0.0) -> list[dict[str, Any]]:
    """Деньги и минуты на узел и на минуту видео. Знаки ElevenLabs переводятся в деньги только по цене, которую дал человек."""
    metrics, edits = read_metrics(workspace() / "metrics.csv"), _edits()
    rows: list[dict[str, Any]] = []
    for chapter in chapter_ids:
        own = [m for m in metrics if m.chapter == chapter]
        nodes = len(read_or(workspace() / "work" / chapter / "layer.json", {"nodes": []})["nodes"])
        audio = [read(p)["audio_check"] for p in sorted((workspace() / "out" / chapter / "videos").glob("*.passport.json"))]
        video_minutes = sum(a["duration_s"] for a in audio) / 60
        chars = sum(a.get("paid_chars", 0) for a in audio)
        video_usd = sum(m.money_usd for m in own if m.stage == "video") + chars / 1000 * usd_per_1k_chars
        other_usd = sum(m.money_usd for m in own if m.stage != "video")
        hand = [e for e in edits if e.get("chapter") == chapter]
        video_hand = sum(_minutes(e) for e in hand if "video" in (e.get("file") or ""))
        person = sum(_minutes(e) for e in hand) + sum(m.person_minutes for m in own)
        rows = [*rows, {
            "chapter": chapter, "nodes": nodes, "usd": round(other_usd + video_usd, 2), "usd_per_node": round(other_usd / nodes, 3) if nodes else None,
            "person_minutes": person, "person_minutes_per_node": round((person - video_hand) / nodes, 2) if nodes else None,
            "mentor_minutes": sum(m.mentor_minutes for m in own), "video_minutes": round(video_minutes, 2),
            "usd_per_video_minute": round(video_usd / video_minutes, 2) if video_minutes else None,
            "person_minutes_per_video_minute": round(video_hand / video_minutes, 2) if video_minutes else None, "elevenlabs_chars": chars,
            "manual_edits": len(hand), "manual_share": round(len({e.get("file") for e in hand}) / nodes, 3) if nodes else None,
        }]
    return rows


def build_process(chapter_ids: Sequence[str]) -> Path:
    price = float(os.environ.get("ELEVENLABS_USD_PER_1K", "0") or 0)
    rows = process_rows([c for c in chapter_ids if (workspace() / "work" / c / "layer.json").exists()], price)
    out = workspace() / "out" / "process.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else ["chapter"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        log.info("%s", "; ".join(f"{k}={v}" for k, v in row.items()))
    log.info("процесс: %s", out)
    return out


# ---------- перенос: держит ли конвейер качество на незнакомой главе

TRAINING = ("latyshova_gl5_par17-20", "basniev_gl23-24_1", "kuznetsov_gl10")
CONTROL = ("vendelshtein_gl1", "barenblatt_par4", "baraboshkin_par1-2")
# по этим столбцам меряется падение от обучения; у остальных выше — лучше, у flagged_share и early_terms — хуже
COMPARED = ("claims_per_page", "covered_share", "flagged_share", "verify_follows", "tasks")
LOWER_IS_BETTER = frozenset({"flagged_share"})


def _split(chapter: str) -> str:
    return "обучение" if chapter in TRAINING else "контроль" if chapter in CONTROL else "тест или репетиция"


def _pages(meta: Mapping[str, Any]) -> int:
    return sum(int(b) - int(a) + 1 for a, b in meta.get("pages") or [])


def _share(part: float, whole: float) -> float | None:
    return round(part / whole, 3) if whole else None


def quality_rows(chapters: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Качество слоя и курса по главам из файлов главы, без модели. Глава без слоя пропускается."""
    money = {r["chapter"]: r for r in process_rows([c for c in chapters if (workspace() / "work" / c / "layer.json").exists()])}
    rows: list[dict[str, Any]] = []
    for chapter, meta in chapters.items():
        work = workspace() / "work" / chapter
        if chapter not in money:
            continue
        nodes = read(work / "layer.json")["nodes"]
        claims = sum(len(n["claims"]) for n in nodes)
        units = read_or(work / "coverage.json", {"rows": []})["rows"]
        audit = read_or(work / "audit.json", {})
        trust = read_or(work / "trust.json", {})
        tasks = read_or(work / "tasks.json", {"tasks": []})
        tasks = tasks.get("tasks", []) if isinstance(tasks, dict) else tasks
        pages = _pages(meta)
        verified = trust.get("claims") or {}
        planned = len(read_or(work / "plan.json", {"nodes": nodes})["nodes"])
        rows = [*rows, {
            "chapter": chapter, "split": _split(chapter), "complete": len(nodes) >= planned, "pages": pages, "nodes": len(nodes), "planned_nodes": planned, "claims": claims,
            "claims_per_page": round(claims / pages, 1) if pages else None,
            "units": len(units), "covered_share": _share(sum(bool(u.get("node_ids")) for u in units), len(units)),
            "skipped_with_reason": sum(not u.get("node_ids") and bool(u.get("reason")) for u in units),
            "units_lost": sum(not u.get("node_ids") and not u.get("reason") for u in units),
            "flagged_share": _share(len(audit.get("flagged") or []), claims) if audit else None,
            "early_terms": len(audit.get("early_terms") or []) if audit else None,
            "verify_follows": _share(verified.get("follows", 0), verified.get("total", 0)) if verified else None,
            "tasks": len(tasks), "task_types": len({t.get("type") for t in tasks}),
            "usd_per_node": money[chapter]["usd_per_node"], "person_minutes": money[chapter]["person_minutes"],
        }]
    return rows


def transfer_drop(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Изменение каждой не обучающей главы против среднего по обучающим, в долях: −0.3 — на 30 % хуже.
    Эталон — только обучающие главы с полным слоем: собранная на три узла глава сравнение исказила бы."""
    base = {k: [r[k] for r in rows if r["split"] == "обучение" and r["complete"] and r[k] is not None] for k in COMPARED}
    mean = {k: sum(v) / len(v) for k, v in base.items() if v}
    drops: list[dict[str, Any]] = []
    for row in (r for r in rows if r["split"] != "обучение"):
        change = {}
        for k, m in mean.items():
            if row[k] is None or not m:
                continue
            delta = (row[k] - m) / m
            change = {**change, k: round(-delta if k in LOWER_IS_BETTER else delta, 3)}
        drops = [*drops, {"chapter": row["chapter"], "complete": row["complete"], **change}]
    return drops


def _table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "нет глав со слоем\n"
    head = list(rows[0])
    line = lambda r: "| " + " | ".join("—" if r.get(k) is None else str(r.get(k)) for k in head) + " |"
    return "\n".join([line({k: k for k in head}), "|" + "---|" * len(head), *(line(r) for r in rows)]) + "\n"


def build_transfer(chapter_ids: Sequence[str]) -> Path:
    """out/transfer.csv и transfer.md: качество по главам и падение от обучения к контролю и тесту."""
    meta = read(workspace() / "chapters.json")["chapters"]
    rows = quality_rows({c: meta.get(c, {}) for c in chapter_ids})
    drops = transfer_drop(rows)
    out = workspace() / "out" / "transfer.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else ["chapter"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    note = ("Считается из файлов главы, без модели. claims_per_page — подробность слоя: меньше, чем на обучении, значит глава сжата. "
            "flagged_share — доля утверждений с расхождением при сверке кодом. verify_follows — доля, которую вторая модель признала следующей из цитаты (если запускали verify).\n\n"
            "Падение — изменение против среднего по обучающим главам с полным слоем: −0.3 значит на 30 % хуже, для flagged_share знак перевёрнут. "
            "complete=False — слой собран не на все узлы плана, сравнение по такой главе предварительное.\n")
    (out.with_suffix(".md")).write_text(f"# Перенос конвейера\n\n{note}\n## Главы\n\n{_table(rows)}\n## Падение от обучения\n\n{_table(drops)}", encoding="utf-8")
    for row in drops:
        log.info("%s", "; ".join(f"{k}={v}" for k, v in row.items()))
    log.info("перенос: %s", out.with_suffix(".md"))
    return out
