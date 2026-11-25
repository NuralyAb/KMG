"""Команды конвейера. Одна команда на главу: glava build <глава>."""

import argparse
import logging
import os
from pathlib import Path

from glava.modules.library.api import LibraryError
from glava.modules.llm.api import BudgetExceeded, ProviderUnavailable
from glava.pipeline.chapter import load_chapter
from glava.pipeline.runtime import open_provider, verifier_env
from glava.pipeline.steps.audit import build_audit
from glava.pipeline.steps.course import build_site
from glava.pipeline.steps.errata import build_errata
from glava.pipeline.steps.extract import build_extract
from glava.pipeline.steps.fact import apply_fact, show_fact
from glava.pipeline.steps.illustrations import build_illustrations
from glava.pipeline.steps.layer import build_layer
from glava.pipeline.steps.passport import build_passport
from glava.pipeline.steps.reports import build_process, build_ready, build_templates
from glava.pipeline.steps.review import build_review
from glava.pipeline.steps.routing import build_routing
from glava.pipeline.steps.simulation import build_simulation
from glava.pipeline.steps.tasks import build_tasks
from glava.pipeline.steps.verify import build_verify
from glava.pipeline.steps.video import (
    accept_spec,
    build_video,
    film_spec,
    list_voices,
    rebuild,
)
from glava.shared.json_files import read
from glava.shared.json_schemas import load_schema
from glava.shared.paths import workspace

log = logging.getLogger("glava")
COMMANDS = ["build", "errata", "layer", "routing", "tasks", "illustrations", "course", "review", "video", "rebuild", "voices", "templates", "ready", "process",
            "simulation", "units", "extract", "audit", "verify", "fact", "passport"]
TRAINING = ("latyshova_gl5_par17-20", "basniev_gl23-24_1", "kuznetsov_gl10")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="glava", description="Глава книги -> учебный слой -> демо-курс")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("chapter", nargs="?", help="глава; для ready и process можно не указывать — тогда обучающие главы")
    parser.add_argument("--limit", type=int, default=None, help="собрать только первые N узлов")
    parser.add_argument("--package", type=Path, default=None, help="папка чужого пакета для review")
    parser.add_argument("--vision", action="store_true", help="ненадёжные страницы в extract прочитать моделью по изображению (платно)")
    parser.add_argument("--mutants", action="store_true", help="verify: ещё и замерить, сколько внесённой порчи замечает проверяющая модель (платно)")
    parser.add_argument("--node", help="узел для video и simulation")
    parser.add_argument("--format", choices=["short", "wide"], default="short", help="формат ролика")
    parser.add_argument("--template", help="шаблон сцены ролика из доменного пакета")
    parser.add_argument("--spec", type=Path, help="video: собрать ролик из готовой спецификации, модель не нужна")
    parser.add_argument("--spec-only", action="store_true", help="video: только спецификация, без озвучки и рендера — для проверки ментором")
    parser.add_argument("--accept", action="store_true", help="video --spec: фразы сверены с утверждениями, снять пометку «факт изменился»; fact --apply: число вне цитаты подтвердил человек")
    parser.add_argument("--voice", choices=["elevenlabs", "edge"], help="голос ролика; по умолчанию VOICE_PROVIDER")
    parser.add_argument("--until", choices=["design"], help="simulation: остановиться после замысла")
    parser.add_argument("--apply", action="store_true", help="fact: разнести правку факта и пересобрать курс; без ключа только показать, что она задела")
    args = parser.parse_args()
    try:
        run(args, parser)
    except (LibraryError, ProviderUnavailable, BudgetExceeded) as error:
        raise SystemExit(str(error)) from error


def run_reports(args: argparse.Namespace) -> bool:
    """Команды, которым не нужны ни модель, ни текст книги."""
    chapters = [args.chapter] if args.chapter else list(TRAINING)
    if args.command == "voices":
        list_voices()
    elif args.command == "ready":
        if not build_ready(chapters):
            raise SystemExit(1)
    elif args.command == "process":
        build_process([args.chapter] if args.chapter else list(read(workspace() / "chapters.json")["chapters"]))
    elif args.command == "templates" and args.chapter:
        build_templates(args.chapter)
    else:
        return False
    return True


def run_video(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    chapter = load_chapter(args.chapter)
    if args.command == "rebuild":
        # число из исправленного утверждения сперва доходит до текста шага и заданий, потом до роликов
        apply_fact(chapter, build=False, accept=True)
        rebuild(chapter, open_provider, args.node, args.voice)
    elif args.spec and args.accept:
        accept_spec(chapter, args.spec)
    elif args.spec:
        film_spec(chapter, args.spec, args.voice)
    elif args.node and args.template:
        build_video(chapter, open_provider, args.node, args.format, args.template, args.voice, args.spec_only)
    else:
        parser.error("укажите --node и --template или --spec")


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if run_reports(args):
        return
    if not args.chapter:
        parser.error("укажите главу")
    if args.command in ("video", "rebuild"):
        run_video(args, parser)
        return
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
    if args.command == "fact":
        apply_fact(chapter, accept=args.accept) if args.apply else show_fact(chapter)
        return
    if args.command == "passport":
        build_passport(chapter)
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
