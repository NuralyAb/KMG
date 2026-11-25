"""Команды конвейера. Одна команда на главу: glava build <глава>."""

import argparse
import ast
import csv
import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from glava.course.build import build_course
from glava.library import CHAPTER_PREFIX, SAFE_ID, LibraryError, library_chapter, load_source, unsure_pages
from glava.library.extract import extract_pages, to_md
from glava.library.preview import make_previews
from glava.library.vision import read_page
from glava.llm import BudgetExceeded, Provider, Reply, cached, metered
from glava.llm.errors import ProviderUnavailable
from glava.llm.providers import provider_from_env
from glava.review.engine import load_package, review_package, workspace
from glava.scenes import load_style, load_templates
from glava.stages.enrich import apply, make_enrichment
from glava.stages.errata import make_errata, render_page
from glava.stages.illustrations import make_illustrations, records
from glava.stages.layer import coverage_rows, drop_unsupported, load_schema, make_node, make_plan, pages_of, plan_issues
from glava.stages.routing import make_routing
from glava.stages.tasks import chapter_task_issues, groups, make_tasks, number_tasks
from glava.trust.audit import audit_layer
from glava.trust.entail import CLAIM_GROUP, check_claims, source_of, trust_report, verify_node
from glava.trust.mutate import measure, mutants
from glava.units import Unit, mark_unsure, parse_units, read_pages

ROOT = Path(__file__).resolve().parents[2]
PARALLEL = 4
MODEL_MUTANTS = 20
BUDGET_USD = float(os.environ.get("GLAVA_BUDGET_USD", "25"))
METRIC_FIELDS = ("chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes", "mentor_minutes",
                 "video_seconds", "manual_share")
log = logging.getLogger("glava")


@dataclass(frozen=True)
class Chapter:
    chapter_id: str
    prefix: str
    title: str
    book: str
    domain: Path
    units: tuple[Unit, ...]
    source: str
    pdf: Path | None = None

    @property
    def work(self) -> Path:
        return ROOT / "work" / self.chapter_id

    @property
    def errata_file(self) -> Path:
        return self.domain / "errata" / f"{self.chapter_id}.json"


def load_chapter(chapter_id: str) -> Chapter:
    registry = json.loads((ROOT / "chapters.json").read_text(encoding="utf-8"))
    info = registry["chapters"].get(chapter_id)
    if info is None:
        # глава реестра главнее: загруженная книга не может её подменить
        own = library_chapter(ROOT, chapter_id)
        if own is None:
            raise LibraryError(f"главы {chapter_id} нет ни в chapters.json, ни в базе знаний")
        return load_library_chapter(chapter_id, own)
    # загруженные книги лежат в своей папке, файлы организаторов — в общей
    texts, scans = (info["root"], info["root"]) if info.get("root") else (os.environ.get("GLAVA_BOOKS", registry["root"]), os.environ.get("GLAVA_PDFS", registry["pdf_root"]))
    md = (ROOT / texts / info["file"]).read_text(encoding="utf-8-sig")
    units = parse_units(read_pages(md, [tuple(r) for r in info["pages"]]))
    return Chapter(chapter_id, info["prefix"], info["title"], info["book"], ROOT / "domain" / info["domain"], tuple(units), info["file"],
                   ROOT / scans / info["pdf"] if info.get("pdf") else None)


def load_library_chapter(chapter_id: str, info: Mapping[str, Any]) -> Chapter:
    """Глава из загруженной книги: текст и PDF лежат рядом в library/<источник>/."""
    source = load_source(ROOT, info["source"])
    if not source.text.exists():
        raise LibraryError("текст книги ещё не извлечён: выполните glava extract")
    pages = read_pages(source.text.read_text(encoding="utf-8"), [tuple(r) for r in info["pages"]])
    units = mark_unsure(parse_units(pages), unsure_pages(source))
    return Chapter(chapter_id, info["prefix"], info["title"], info["book"], ROOT / "domain" / info["domain"], tuple(units), source.original.name, source.pdf)


def build_extract(source_id: str, with_model: bool) -> None:
    """Загруженный файл -> страницы md и отчёт, каким страницам можно верить."""
    source = load_source(ROOT, source_id)
    pages = extract_pages(source.original, source.kind, source.folder / "scan.pdf")
    if source.pdf is not None:
        make_previews(source.pdf, source.folder / "preview")
    weak = [p for p in pages if p.state in ("scan", "doubtful")]
    if with_model and source.pdf is not None and weak:
        provider, prompt = open_provider(), prompt_file("extract")
        pdf, folder = source.pdf, source.folder / "scans"
        with ThreadPoolExecutor(PARALLEL) as pool:
            read_again = {p.page: (p, rs) for p, rs in pool.map(lambda p: read_page(provider, prompt, p, pdf, folder), weak)}
        pages = [read_again[p.page][0] if p.page in read_again else p for p in pages]
        replies = [r for _, rs in read_again.values() for r in rs]
        append_metrics(source_id, "extract", len(weak), replies)
        log.info("моделью прочитано страниц: %s, $%.2f", sum(p.method == "vision" for p in pages), sum(r.cost_usd for r in replies))
    source.text.write_text(to_md(pages), encoding="utf-8", newline="\n")
    save(source.pages, {"source": source_id, "pages": [p.record() for p in pages]})
    states = Counter(p.state for p in pages)
    log.info("страниц %s: надёжных %s, сверить %s, без текста %s, пустых %s", len(pages), states["text"], states["doubtful"], states["scan"], states["empty"])


def open_provider(env: Mapping[str, str] | None = None) -> Provider:
    return cached(metered(provider_from_env(os.environ if env is None else env), BUDGET_USD), ROOT / ".cache")


def verifier_env(env: Mapping[str, str]) -> dict[str, str]:
    """Проверяющая модель задаётся отдельно: LLM_VERIFY_MODEL, по умолчанию та же. Своя ошибка самому себе видна хуже."""
    model = env.get("LLM_VERIFY_MODEL")
    return {**env, "LLM_MODEL": model} if model else dict(env)


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_file(name: str) -> str:
    return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def context_of(chapter: Chapter) -> str:
    misconceptions = read(chapter.domain / "misconceptions.json")
    listed = "\n".join(f"{m['id']}: {m['text']}" for m in misconceptions)
    difficulty = (chapter.domain / "difficulty.md").read_text(encoding="utf-8")
    return f"# Глава\n{chapter.title}. {chapter.book}\n\n# Заблуждения новичков\n{listed}\n\n# {difficulty}"


def write_metrics(chapter: Chapter, stage: str, nodes: int, replies: Sequence[Reply], video_seconds: float = 0) -> None:
    append_metrics(chapter.chapter_id, stage, nodes, replies, video_seconds)


def append_metrics(chapter_id: str, stage: str, nodes: int, replies: Sequence[Reply], video_seconds: float = 0) -> None:
    path = ROOT / "metrics.csv"
    is_new = not path.exists()
    row = [chapter_id, stage, nodes, sum(r.input_tokens for r in replies), sum(r.output_tokens for r in replies),
           f"{sum(r.cost_usd for r in replies):.4f}", 0, 0, video_seconds, 0]
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        if is_new:
            writer.writerow(METRIC_FIELDS)
        writer.writerow(row)


def build_errata(chapter: Chapter, provider: Provider) -> None:
    """Сверка md со сканом. Без PDF этап пропускается: лист опечаток остаётся пустым."""
    if chapter.pdf is None or not chapter.pdf.exists():
        log.info("PDF главы не указан, лист опечаток пропущен")
        return
    pages, prompt = pages_of(chapter.units), prompt_file("errata")
    images = {n: render_page(chapter.pdf, n, chapter.work / "scans") for n in pages}
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda n: make_errata(provider, prompt, n, pages[n], images[n]), pages))
    entries = [e for found, _ in results for e in found]
    save(chapter.errata_file, {"chapter": chapter.chapter_id, "entries": entries})
    write_metrics(chapter, "errata", len(pages), [r for _, rs in results for r in rs])
    log.info("лист опечаток: %s записей, из них подозрительных мест издания: %s", len(entries), sum(e["kind"] == "suspect" for e in entries))


def enrich_nodes(chapter: Chapter, provider: Provider, nodes: Sequence[dict], errata: Sequence[dict]) -> tuple[list[dict], list[Reply], list[str]]:
    """Блоки страницы шага. Узел, который модель не дополнила, остаётся как был и попадает в отчёт."""
    note = chapter.domain / "now_practice.md"
    prompt, now = prompt_file("enrich"), note.read_text(encoding="utf-8") if note.exists() else ""

    def rows_for(part: Sequence[dict]) -> tuple[dict[str, dict], list[Reply]]:
        return make_enrichment(provider, prompt, part, now, errata)

    with ThreadPoolExecutor(PARALLEL) as pool:
        first = list(pool.map(rows_for, groups(nodes)))
        done = {k for found, _ in first for k in found}
        second = list(pool.map(rows_for, [[n] for n in nodes if n["id"] not in done]))
    rows = {k: v for found, _ in (*first, *second) for k, v in found.items()}
    units = chapter.units
    return [apply(n, rows.get(n["id"]), units, errata) for n in nodes], [r for _, rs in (*first, *second) for r in rs], [n["id"] for n in nodes if n["id"] not in rows]


def build_layer(chapter: Chapter, provider: Provider, limit: int | None = None) -> dict[str, Any]:
    context = context_of(chapter)
    errata = errata_of(chapter)
    plan, plan_replies = make_plan(provider, prompt_file("plan"), context, chapter.units)
    save(chapter.work / "plan.json", plan)
    unfixed = plan_issues(plan, chapter.units)
    if unfixed:
        raise SystemExit("план главы не прошёл проверку: " + "; ".join(unfixed[:5]))
    count = min(limit or len(plan["nodes"]), len(plan["nodes"]))
    log.info("план: узлов %s, собираю %s", len(plan["nodes"]), count)

    def one(index: int) -> tuple[dict, list[str], list[Reply]]:
        return make_node(provider, prompt_file("node"), context, plan, index, chapter.units, chapter.prefix, errata)

    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(one, range(count)))
    pages = pages_of(chapter.units)
    cleaned = [drop_unsupported(node, pages, errata) for node, _, _ in results]
    nodes, enrich_replies, plain = enrich_nodes(chapter, provider, [node for node, _ in cleaned], errata)
    layer = {
        "chapter": chapter.chapter_id, "source": chapter.source, "pdf_pages": sorted({str(u.page_pdf) for u in chapter.units}),
        "generated_by": f"{provider.name}/{provider.model}", "title": chapter.title, "book": chapter.book,
        "parts": [{"title": p["title"], "nodes": [f"{chapter.prefix}.{s}" for s in p["slugs"]]} for p in plan["parts"]],
        "nodes": nodes,
    }
    report = {"issues": {node["id"]: issues for node, issues, _ in results if issues},
              "dropped_claims": [cid for _, dropped in cleaned for cid in dropped],
              "not_enriched": plain, "nodes": len(layer["nodes"]), "claims": sum(len(n["claims"]) for n in layer["nodes"])}
    save(chapter.work / "layer.json", layer)
    save(chapter.work / "coverage.json", {"chapter": chapter.chapter_id, "rows": coverage_rows(plan, chapter.units, chapter.prefix)})
    save(chapter.work / "layer_report.json", report)
    replies = [*plan_replies, *(r for _, _, rs in results for r in rs), *enrich_replies]
    write_metrics(chapter, "layer", len(layer["nodes"]), replies)
    broken = [n for n, found in report["issues"].items() if any(i.startswith("схема") for i in found)]
    if broken:
        raise SystemExit(f"узлы не прошли схему: {', '.join(broken)}; слой сохранён, повторите команду")
    log.info("слой: узлов %s, утверждений %s, отброшено %s, замечания в узлах: %s, $%.2f", report["nodes"], report["claims"],
             len(report["dropped_claims"]), len(report["issues"]), sum(r.cost_usd for r in replies))
    return layer


def errata_of(chapter: Chapter) -> list[dict]:
    """Лист опечаток этапа errata и записи человека из <глава>.manual.json."""
    files = (chapter.errata_file, chapter.errata_file.with_suffix(".manual.json"))
    return [e for file in files for e in read_or(file, {"entries": []})["entries"]]


def routing_context(chapter: Chapter) -> str:
    pictures = [t.SUMMARY for t in load_templates(chapter.domain / "templates").values()]
    videos = [line for file in sorted((chapter.domain / "video").glob("*.py")) if (line := template_summary(file))]
    difficulty = (chapter.domain / "difficulty.md").read_text(encoding="utf-8")
    return "\n".join(["Рисунки и интерактив:", *pictures, "", "Видео:", *videos, "", difficulty])


def template_summary(file: Path) -> str:
    """SUMMARY видеошаблона читается из текста: для рендера нужен cairo, а для маршрутизации нет."""
    for node in ast.parse(file.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SUMMARY" for t in node.targets) and isinstance(node.value, ast.Constant):
            return str(node.value.value)
    return ""


def build_routing(chapter: Chapter, provider: Provider) -> None:
    routing, replies = make_routing(provider, prompt_file("routing"), read(chapter.work / "layer.json"), routing_context(chapter))
    save(chapter.work / "routing.json", routing)
    write_metrics(chapter, "routing", len(routing["routes"]), replies)
    log.info("маршруты: %s", len(routing["routes"]))


def build_tasks(chapter: Chapter, provider: Provider) -> None:
    nodes = read(chapter.work / "layer.json")["nodes"]
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda g: make_tasks(provider, prompt_file("tasks"), g), groups(nodes)))
    tasks = number_tasks(t for found, _ in results for t in found)
    save(chapter.work / "tasks.json", {"chapter": chapter.chapter_id, "tasks": tasks})
    write_metrics(chapter, "tasks", len(nodes), [r for _, rs in results for r in rs])
    log.info("задания: %s; замечания: %s", len(tasks), chapter_task_issues(tasks) or "нет")


def build_illustrations(chapter: Chapter, provider: Provider) -> None:
    nodes = read(chapter.work / "layer.json")["nodes"]
    templates, style = load_templates(chapter.domain / "templates"), load_style(chapter.domain)
    prompt = prompt_file("illustrations")
    errata = errata_of(chapter)

    def scenes_for(part: Sequence[dict]) -> tuple[list[dict], list[Reply]]:
        return make_illustrations(provider, prompt, part, templates, style, errata)

    with ThreadPoolExecutor(PARALLEL) as pool:
        first = list(pool.map(scenes_for, groups(nodes)))
        drawn = {s["node_id"] for found, _ in first for s in found}
        # узлы без рисунка спрашиваются ещё раз по одному
        second = list(pool.map(scenes_for, [[n] for n in nodes if n["id"] not in drawn]))
    results = [*first, *second]
    found = records([s for scenes, _ in results for s in scenes], nodes, templates, style, chapter.work / "pictures")
    save(chapter.work / "illustrations.json", {"chapter": chapter.chapter_id, "illustrations": found})
    write_metrics(chapter, "illustrations", len(nodes), [r for _, rs in results for r in rs])
    without = sorted({n["id"] for n in nodes} - {r["step_id"] for r in found})
    log.info("иллюстрации: %s; шаги без рисунка: %s", len(found), without or "нет")


def layer_of(chapter_id: str) -> tuple[Path, dict[str, Any]]:
    """Слой главы по имени: этим командам не нужны ни md, ни PDF."""
    if not SAFE_ID.fullmatch(chapter_id):
        raise LibraryError("глава: недопустимое имя")
    work = ROOT / "work" / chapter_id
    if not (work / "layer.json").exists():
        raise LibraryError(f"слой главы {chapter_id} ещё не собран")
    return work, read(work / "layer.json")


def file_digest(path: Path) -> str:
    """По нему видно, о каком слое отчёт: время файла об этом не говорит."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_audit(chapter_id: str) -> dict[str, Any]:
    """Бесплатно: сверка слоя кодом и замер, насколько эта сверка чутка."""
    work, layer = layer_of(chapter_id)
    claims = [c for n in layer["nodes"] for c in n["claims"]]
    report = {**audit_layer(layer), "sensitivity": measure(claims), "layer_sha256": file_digest(work / "layer.json")}
    save(work / "audit.json", report)
    sense = report["sensitivity"]
    log.info("утверждений %s, с расхождениями %s %s; терминов раньше объяснения %s; порчи поймано %s из %s", report["claims"], len(report["flagged"]),
             report["by_flag"], len(report["early_terms"]), sense["caught"], sense["made"])
    return report


def build_verify(chapter_id: str, provider: Provider, with_mutants: bool) -> dict[str, Any]:
    """Платно: вторая модель сверяет утверждения с цитатами и фразы с утверждениями."""
    work, layer = layer_of(chapter_id)
    digest = file_digest(work / "layer.json")  # пока модель отвечает, слой могут изменить
    prompts = {"claims": prompt_file("verify_claims"), "prose": prompt_file("verify_prose")}
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda n: verify_node(provider, prompts, n), layer["nodes"]))
    report = trust_report(chapter_id, f"{provider.name}/{provider.model}", [c for cs, _, _ in results for c in cs], [p for _, ps, _ in results for p in ps], layer["nodes"])
    report["layer_sha256"] = digest
    replies = [r for _, _, rs in results for r in rs]
    if with_mutants:
        report["sensitivity"], asked = model_sensitivity(provider, prompts["claims"], layer, report)
        replies += asked
    save(work / "trust.json", report)
    append_metrics(chapter_id, "verify", len(layer["nodes"]), replies)
    log.info("утверждения: %s; фразы: %s; $%.2f", report["claims"], report["prose"], sum(r.cost_usd for r in replies))
    if report["claims"]["unchecked"] == report["claims"]["total"]:
        raise LibraryError("проверяющая модель не вынесла ни одного вердикта: ничего не проверено")
    return report


def model_sensitivity(provider: Provider, prompt: str, layer: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, Any], list[Reply]]:
    """Испорченные утверждения вперемешку с нетронутыми: видно и чутьё проверяющего, и ложные тревоги.

    Портятся только утверждения, которые он до порчи признал верными.
    """
    weak = {r["id"] for r in report["weak"]}
    claims = [c for n in layer["nodes"] for c in n["claims"] if c["id"] not in weak]
    shuffle = random.Random(0)
    made = list(mutants(claims, per_kind=MODEL_MUTANTS))
    calm = shuffle.sample(sorted(claims, key=lambda c: c["id"]), min(len(made), len(claims)))
    mixed = [(m.kind, m.text, m.quote) for m in made] + [("control", c["text"], source_of(c)) for c in calm]
    shuffle.shuffle(mixed)
    items = [{"id": f"m{i}", "text": text, "quote": quote} for i, (_, text, quote) in enumerate(mixed)]
    parts = [items[i:i + CLAIM_GROUP] for i in range(0, len(items), CLAIM_GROUP)]
    with ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda p: check_claims(provider, prompt, p), parts))
    verdicts = {r["id"]: r["verdict"] for rows, _ in results for r in rows}
    rows: dict[str, dict[str, int]] = {}
    for i, (kind, _, _) in enumerate(mixed):
        if verdicts[f"m{i}"] != "unchecked":
            row = rows.setdefault(kind, {"made": 0, "caught": 0})
            row["made"] += 1
            row["caught"] += verdicts[f"m{i}"] != "follows"
    controls = rows.pop("control", {"made": 0, "caught": 0})
    total, caught = sum(k["made"] for k in rows.values()), sum(k["caught"] for k in rows.values())
    found = {"kinds": rows, "made": total, "caught": caught, "recall": round(caught / total, 3) if total else None, "controls": controls,
             "unchecked": sum(v == "unchecked" for v in verdicts.values())}
    return found, [r for _, rs in results for r in rs]


def read_or(path: Path, default: Any) -> Any:
    return read(path) if path.exists() else default


def build_site(chapter: Chapter) -> Path:
    work = chapter.work
    layer = read(work / "layer.json")
    out = build_course(layer, read_or(work / "routing.json", {"routes": []}), read_or(work / "tasks.json", {"tasks": []})["tasks"],
                       read_or(work / "illustrations.json", {"illustrations": []})["illustrations"], ROOT / "out" / chapter.chapter_id, work / "pictures",
                       simulations=work / "simulations.json")
    log.info("курс: %s", out / "index.html")
    return out


def build_review(chapter: Chapter, source: Path, provider: Provider) -> Path:
    """Проверка чужого пакета; ответ — out/review/<пакет>.json."""
    if chapter.chapter_id.startswith(CHAPTER_PREFIX):
        raise LibraryError("проверка пакета по главе базы знаний не поддерживается: ответ с цитатами книги попал бы в git")
    package = load_package(source)
    folder = workspace(source, ROOT / "work" / "review", package["package_id"])
    prompts = {role: prompt_file(f"review_{role}") for role in ("find", "physics", "judge")}
    checklist = (chapter.domain / "physics_checklist.json").read_text(encoding="utf-8")
    answer, replies = review_package(package, pages_of(chapter.units), provider, prompts, checklist, folder)
    target = ROOT / "out" / "review" / f"{package['package_id']}.json"
    save(target, answer)
    write_metrics(chapter, "review", len(package["items"]) + len(package["frames"]), replies)
    log.info("замечаний %s, $%.2f, ответ: %s", len(answer["remarks"]), sum(r.cost_usd for r in replies), target)
    return target


def build_video(chapter: Chapter, provider: Provider, node_id: str, kind: str, template_name: str) -> None:
    """Ролик по одному узлу. Нужны пакеты группы video (pycairo, edge-tts, faster-whisper) и ffmpeg."""
    from glava.scenes import load_module
    from glava.video.produce import produce
    from glava.video.spec import make_spec

    node = next((n for n in read(chapter.work / "layer.json")["nodes"] if n["id"] == node_id), None)
    if node is None:
        raise SystemExit(f"узла {node_id} нет в слое")
    template = load_module(chapter.domain / "video" / f"{template_name}.py")
    checklist = read(chapter.domain / "physics_checklist.json")
    video_id = f"{node_id.replace('.', '_')}_{kind}"
    spec, replies = make_spec(provider, prompt_file("video"), node, template, template_name, checklist, kind, video_id, chapter.chapter_id)
    passport = produce(spec, node, template, load_style(chapter.domain), (chapter.domain / "pronunciation.md").read_text(encoding="utf-8"), checklist,
                       chapter.work / "videos", ROOT / "out" / chapter.chapter_id / "videos")
    write_metrics(chapter, "video", 1, replies, passport["audio_check"]["duration_s"])


def build_simulation(chapter: Chapter, node_id: str, until: str | None) -> None:
    """3D-симулятор по узлу слоя. Конвейер сцен — на Node.js, потолки расхода — simulators/agent/steps.json."""
    if node_id not in {n["id"] for n in read(chapter.work / "layer.json")["nodes"]}:
        raise SystemExit(f"в слое нет узла {node_id}")
    program, folder = shutil.which("node"), ROOT / "simulators"
    if program is None or not (folder / "node_modules").is_dir():
        raise SystemExit("нужен Node.js 22; один раз выполните: cd simulators; npm ci")
    job = re.sub(r"[^a-z0-9_]+", "_", node_id.lower())
    state = folder / "jobs" / job / "state.json"
    before = len(read_or(state, {}).get("spend", []))
    command = [program, "agent/pipeline.mjs", job, "--chapter", chapter.chapter_id, "--node", node_id, *(["--to", until] if until else [])]
    code = subprocess.run(command, cwd=folder, check=False).returncode  # noqa: S603 — аргументы проверены по слою
    spent = [SimpleNamespace(input_tokens=s.get("in") or 0, output_tokens=s.get("out") or 0, cost_usd=s.get("usd") or 0)
             for s in read_or(state, {}).get("spend", [])[before:]]
    if spent:
        write_metrics(chapter, "simulation", 1, spent)
    if code:
        raise SystemExit(code)
    if not until:
        build_site(chapter)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="glava", description="Глава книги -> учебный слой -> демо-курс")
    parser.add_argument("command", choices=["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "review", "video", "simulation", "units", "extract", "audit", "verify"])
    parser.add_argument("chapter")
    parser.add_argument("--limit", type=int, default=None, help="собрать только первые N узлов")
    parser.add_argument("--package", type=Path, default=None, help="папка чужого пакета для review")
    parser.add_argument("--vision", action="store_true", help="ненадёжные страницы в extract прочитать моделью по изображению (платно)")
    parser.add_argument("--mutants", action="store_true", help="verify: ещё и замерить, сколько внесённой порчи замечает проверяющая модель (платно)")
    parser.add_argument("--node", help="узел для video и simulation")
    parser.add_argument("--format", choices=["short", "wide"], default="short", help="формат ролика")
    parser.add_argument("--template", help="шаблон сцены ролика из доменного пакета")
    parser.add_argument("--until", choices=["design"], help="simulation: остановиться после замысла")
    args = parser.parse_args()
    try:
        run(args, parser)
    except (LibraryError, ProviderUnavailable, BudgetExceeded) as error:
        raise SystemExit(str(error)) from error


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.command == "extract":
        build_extract(args.chapter, args.vision)
        return
    if args.command == "audit":
        build_audit(args.chapter)
        return
    if args.command == "verify":
        build_verify(args.chapter, open_provider(verifier_env(os.environ)), args.mutants)
        return
    chapter = load_chapter(args.chapter)
    load_schema("node")
    if args.command == "units":
        for unit in chapter.units:
            log.info("%s %s %s", unit.unit_id, unit.kind, unit.excerpt)
        return
    if args.command == "course":
        build_site(chapter)
        return
    if args.command == "simulation":
        if not args.node:
            parser.error("укажите --node")
        build_simulation(chapter, args.node, args.until)
        return
    provider = open_provider()
    if args.command == "review":
        if args.package is None:
            parser.error("укажите --package")
        build_review(chapter, args.package, provider)
        return
    if args.command == "video":
        if not args.node or not args.template:
            parser.error("укажите --node и --template")
        build_video(chapter, provider, args.node, args.format, args.template)
        return
    if args.command in ("build", "errata"):
        build_errata(chapter, provider)
    if args.command in ("build", "layer"):
        build_layer(chapter, provider, args.limit)
        build_audit(chapter.chapter_id)
    if args.command in ("build", "routing"):
        build_routing(chapter, provider)
    if args.command in ("build", "tasks"):
        build_tasks(chapter, provider)
    if args.command in ("build", "illustrations"):
        build_illustrations(chapter, provider)
    if args.command == "build":
        build_site(chapter)


if __name__ == "__main__":
    main()
