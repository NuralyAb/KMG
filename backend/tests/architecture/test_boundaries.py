"""Границы модулей. Правила записаны в backend/architecture.toml; тест сверяет их с настоящими импортами."""

import ast
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[3]
PACKAGE = REPOSITORY / "backend" / "glava"
RULES = tomllib.loads((REPOSITORY / "backend" / "architecture.toml").read_text(encoding="utf-8"))
MODULES = {p.name for p in (PACKAGE / "modules").iterdir() if (p / "__init__.py").exists()}
# имя импорта не всегда совпадает с именем пакета
DISTRIBUTIONS = {"cairo": "pycairo", "pymupdf": "pymupdf", "fitz": "pymupdf", "edge_tts": "edge-tts", "faster_whisper": "faster-whisper", "imageio_ffmpeg": "imageio-ffmpeg"}


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.level == 0, f"{path}: относительный импорт прячет границу"
            found |= {f"{node.module}.{a.name}" for a in node.names}
    return found


FILES = {p: imports_of(p) for p in PACKAGE.rglob("*.py")}


def layer_of(path: Path) -> str:
    return path.relative_to(PACKAGE).parts[0]


def module_of(name: str) -> str | None:
    found = re.match(r"glava\.modules\.(\w+)", name)
    return found[1] if found and found[1] in MODULES else None


def own_module(path: Path) -> str | None:
    parts = path.relative_to(PACKAGE).parts
    return parts[1] if parts[0] == "modules" and len(parts) > 2 else None


@pytest.mark.parametrize("path", sorted(FILES), ids=lambda p: p.relative_to(PACKAGE).as_posix())
def test_layers_look_only_down(path: Path) -> None:
    if path.parent == PACKAGE:
        return
    allowed = {layer_of(path), *RULES["layers"][layer_of(path)]}
    used = {n.split(".")[1] for n in FILES[path] if n.startswith("glava.")}
    assert used <= allowed, f"слой {layer_of(path)} не может зависеть от {used - allowed}"


@pytest.mark.parametrize("path", sorted(FILES), ids=lambda p: p.relative_to(PACKAGE).as_posix())
def test_modules_are_entered_only_through_the_door(path: Path) -> None:
    own, doors = own_module(path), {"api"}
    if path.relative_to(PACKAGE).as_posix() == "entrypoints/http/app.py":
        doors = {"api", "module"}
    if layer_of(path) == "sdk":
        doors = {"api", "frame_api"}
    for name in FILES[path]:
        other = module_of(name)
        if other and other != own:
            door = name.split(".")[3]
            assert door in doors, f"{name}: внутренности чужого модуля; импортируйте glava.modules.{other}.api"


def real_dependencies() -> dict[str, set[str]]:
    real: dict[str, set[str]] = {m: set() for m in MODULES}
    for path, names in FILES.items():
        if own := own_module(path):
            real[own] |= {m for n in names if (m := module_of(n)) and m != own}
    return real


def test_declared_dependencies_match_the_code() -> None:
    declared = {m: set(d) for m, d in RULES["modules"].items()}
    assert declared == real_dependencies(), "поправьте backend/architecture.toml или уберите лишнюю зависимость"


def test_modules_form_no_cycles() -> None:
    graph, state = real_dependencies(), defaultdict(int)

    def visit(module: str, way: tuple[str, ...]) -> None:
        assert state[module] != 1, f"цикл: {' → '.join((*way, module))}"
        if state[module] == 0:
            state[module] = 1
            for other in graph[module]:
                visit(other, (*way, module))
            state[module] = 2

    for module in graph:
        visit(module, ())


def test_public_api_is_explicit_and_used() -> None:
    """Имя в api.py кто-то импортирует снаружи: иначе это не договор, а случайность."""
    used: dict[str, set[str]] = defaultdict(set)
    for path, names in FILES.items():
        for name in names:
            other = module_of(name)
            if other and other != own_module(path) and ".api." in name:
                used[other].add(name.rsplit(".", 1)[1])
    for module in MODULES:
        api = PACKAGE / "modules" / module / "api.py"
        if api.exists():
            tree = ast.parse(api.read_text(encoding="utf-8"))
            exported = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "__all__")
            assert set(exported) == used[module], f"{module}/api.py: лишнее {set(exported) - used[module]}, нет {used[module] - set(exported)}"


def test_no_transitive_packages() -> None:
    """Каждый внешний пакет, который импортирует код, назван в pyproject.toml прямо, а не пришёл с чужим."""
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    listed = [*project["project"]["dependencies"], *project["dependency-groups"]["video"], *(d for extra in project["project"]["optional-dependencies"].values() for d in extra)]
    direct = {re.match(r"[A-Za-z0-9_.-]+", d)[0].lower() for d in listed}
    used = {n.split(".")[0] for names in FILES.values() for n in names} - set(sys.stdlib_module_names) - {"glava"}
    missing = {n for n in used if DISTRIBUTIONS.get(n, n).lower() not in direct}
    assert not missing, f"добавьте в зависимости: {missing}"


@pytest.mark.parametrize(("entry", "foreign"), [("glava.entrypoints.cli", ("fastapi", "uvicorn", "cairo")), ("glava.entrypoints.http.app", ("pymupdf", "fitz", "cairo", "glava.pipeline"))])
def test_entrypoints_do_not_drag_each_other(entry: str, foreign: tuple[str, ...]) -> None:
    """Сервер не грузит конвейер (он запускается отдельным процессом), конвейер не грузит веб-сервер."""
    code = f"import sys, {entry}; print([m for m in {foreign!r} if m in sys.modules])"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=REPOSITORY / "backend")
    assert done.stdout.strip() == "[]"


def test_only_paths_knows_the_layout() -> None:
    for path in FILES:
        if path.name != "paths.py":
            assert ".parents[" not in path.read_text(encoding="utf-8"), f"{path}: путь к репозиторию берётся из glava.shared.paths"


def test_every_module_says_what_it_is_for() -> None:
    for module in MODULES:
        assert ast.get_docstring(ast.parse((PACKAGE / "modules" / module / "__init__.py").read_text(encoding="utf-8")))
