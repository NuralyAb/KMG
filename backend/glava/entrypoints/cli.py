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
from glava.pipeline.steps.illustrations import build_illustrations
from glava.pipeline.steps.layer import build_layer
from glava.pipeline.steps.review import build_review
from glava.pipeline.steps.routing import build_routing
from glava.pipeline.steps.simulation import build_simulation
from glava.pipeline.steps.tasks import build_tasks
from glava.pipeline.steps.verify import build_verify
from glava.pipeline.steps.video import build_video
from glava.shared.json_schemas import load_schema

log = logging.getLogger("glava")


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
