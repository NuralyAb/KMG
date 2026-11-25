"""Один раз после перехода на новую раскладку: переносит локальные файлы, которых нет в git, в workspace/.

python scripts/migrate_workspace.py            показать, что будет перенесено
python scripts/migrate_workspace.py --apply    перенести
Кэш ответов модели (.cache) остаётся на месте. Существующие файлы не перезаписываются.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace"
OLD = ("library", "published", "books", "work", "out", "domain", "settings.local.json")


def plan() -> list[tuple[Path, Path]]:
    found = []
    for name in OLD:
        source = ROOT / name
        files = [source] if source.is_file() else [p for p in source.rglob("*") if p.is_file()] if source.is_dir() else []
        found += [(f, WORKSPACE / f.relative_to(ROOT)) for f in files]
    return found


def main() -> int:
    moves = plan()
    busy = [(a, b) for a, b in moves if b.exists()]
    for source, target in moves:
        print("занято " if target.exists() else "перенос", source.relative_to(ROOT), "->", target.relative_to(ROOT))
    if "--apply" in sys.argv:
        for source, target in moves:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(source, target)
    print(f"файлов: {len(moves)}, уже есть в workspace: {len(busy)}{'' if '--apply' in sys.argv else '; для переноса добавьте --apply'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
