"""Проверка запроса на запуск и перевод его в аргументы команды."""

from typing import Any

from glava_server.errors import invalid, not_found
from glava_server.names import is_safe_id
from glava_server.repository import Repository
from glava_server.schemas import RunRequest

LIMITED = frozenset({"build", "layer"})
VIDEO_FIELDS = ("node", "format", "template")
OPTIONS = ("limit", *VIDEO_FIELDS, "until")


def _check_video(request: RunRequest, repository: Repository, domain: str) -> None:
    if not request.node or not request.template:
        raise invalid("Для ролика укажите узел и шаблон сцены")
    if not is_safe_id(request.node) or request.node not in {n["id"] for n in repository.nodes(request.chapter)}:
        raise not_found("Такого узла в главе нет")
    if not repository.has_video_template(domain, request.template):
        raise invalid("Такого шаблона сцены в доменном пакете нет")


def _check_node(request: RunRequest, repository: Repository) -> None:
    if not request.node:
        raise invalid("Для симулятора укажите узел")
    if not is_safe_id(request.node) or request.node not in {n["id"] for n in repository.nodes(request.chapter)}:
        raise not_found("Такого узла в главе нет")
    if request.format or request.template:
        raise invalid("Формат и шаблон задаются только для ролика")


def run_args(request: RunRequest, repository: Repository) -> dict[str, Any]:
    """Значимые параметры запуска. Лишний параметр — ошибка: иначе запуск потратит не то, что ждали."""
    chapter = repository.chapter(request.chapter)
    given = {k: v for k, v in request.model_dump(include=set(OPTIONS)).items() if v is not None}
    if "limit" in given and request.command not in LIMITED:
        raise invalid("Ограничение числа узлов есть только у команд build и layer")
    if "until" in given and request.command != "simulation":
        raise invalid("Остановка после замысла есть только у симулятора")
    if request.command == "simulation":
        _check_node(request, repository)
    elif request.command == "video":
        _check_video(request, repository, chapter.domain)
    elif any(f in given for f in VIDEO_FIELDS):
        raise invalid("Узел, формат и шаблон задаются только для ролика")
    return given


def cli_options(args: dict[str, Any]) -> list[str]:
    return [part for name in OPTIONS if name in args for part in (f"--{name}", str(args[name]))]
