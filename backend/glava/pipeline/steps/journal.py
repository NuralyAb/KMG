"""journal: сверка журнала ручных правок (manual_edits.csv) с историей git. Модель и сеть не нужны.

Соглашение о коммитах после заморозки:
- коммит сборки — тема начинается с `run <N>:` или `build:`; в нём меняет файлы глав только конвейер, строк журнала в нём нет;
- любой другой коммит, который меняет файлы главы, — ручной: в том же коммите в журнал добавлены строки,
  поле `file` каждой строки называет изменённый файл или папку (несколько — через `;`).
Файлы, которые после правки пишет сам конвейер (курс в workspace/out/<глава>/ и отчёты из DERIVED), строку не требуют,
если в том же коммите есть строка этой главы.
"""

import csv
import io
import logging
import re
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("glava")

JOURNAL = "manual_edits.csv"
BUILD = re.compile(r"^(run \d+|build)\s*(\([^)]*\))?:", re.IGNORECASE)
CHAPTER_FILE = re.compile(r"^workspace/(?:(work|out)/([^/]+)/|domain/[^/]+/errata/([^/]+?)(?:\.manual)?\.json$)")
# отчёты, которые пишут команды course, rebuild, narrate, audit, templates и fact --apply: их правит не человек
DERIVED = {"audit.json", "narration.json", "template_coverage.json", "stale.json", "layer_report.json"}
LIMIT_MINUTES = 30


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    paths: tuple[str, ...]
    added: tuple[Mapping[str, str], ...] = ()
    removed: tuple[Mapping[str, str], ...] = ()

    @property
    def is_build(self) -> bool:
        return bool(BUILD.match(self.subject))


@dataclass
class Check:
    problems: list[str] = field(default_factory=list)
    minutes: dict[str, float] = field(default_factory=dict)
    no_minutes: dict[str, int] = field(default_factory=dict)
    commits: int = 0


def chapter_of(path: str) -> str | None:
    """Глава, к которой относится файл: workspace/work/<глава>/…, workspace/out/<глава>/…, лист опечаток главы."""
    found = CHAPTER_FILE.match(path)
    if not found:
        return None
    return found.group(2) or found.group(3)


def is_derived(path: str) -> bool:
    return path.startswith("workspace/out/") or (path.startswith("workspace/work/") and path.rsplit("/", 1)[-1] in DERIVED)


def row_files(row: Mapping[str, str]) -> list[str]:
    return [f.strip().replace("\\", "/").rstrip("/") for f in (row.get("file") or "").split(";") if f.strip()]


def covers(row: Mapping[str, str], path: str) -> bool:
    return any(path == f or path.startswith(f + "/") for f in row_files(row))


def rows_of(text: str) -> list[dict[str, str]]:
    return [dict(r) for r in csv.DictReader(io.StringIO(text))] if text.strip() else []


def _key(row: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((k, v or "") for k, v in row.items() if k))


def diff_rows(before: Sequence[Mapping[str, str]], after: Sequence[Mapping[str, str]]) -> tuple[list[Mapping[str, str]], list[Mapping[str, str]]]:
    """Строки, добавленные и удалённые коммитом. Порядок строк не важен, одинаковые строки считаются по числу."""
    old, new = Counter(map(_key, before)), Counter(map(_key, after))
    added = [dict(k) for k in (new - old).elements()]
    removed = [dict(k) for k in (old - new).elements()]
    return added, removed


def _short(commit: Commit) -> str:
    return f"{commit.sha[:7]} «{commit.subject[:60]}»"


def check(commits: Iterable[Commit], chapter: str | None = None, ignored: Iterable[str] = ()) -> Check:
    """Каждая ручная правка файлов главы — со строкой журнала в том же коммите, каждая строка — с правкой."""
    result, ignored = Check(), set(ignored)
    for commit in commits:
        result.commits += 1
        touched = [p for p in commit.paths if chapter_of(p) and (chapter is None or chapter_of(p) == chapter)]
        added = [r for r in commit.added if chapter is None or r.get("chapter") == chapter]
        for row in commit.removed:
            if chapter is None or row.get("chapter") == chapter:
                result.problems.append(f"{_short(commit)}: из журнала удалена строка «{row.get('what_changed', '')[:60]}»")
        if commit.is_build:
            for row in added:
                result.problems.append(f"{_short(commit)}: строка журнала в коммите сборки; ручную правку — отдельным коммитом ({row.get('file')})")
            continue
        journaled = {r.get("chapter") for r in added}
        bare = [p for p in touched if not any(covers(r, p) for r in added) and not (is_derived(p) and chapter_of(p) in journaled)]
        if bare:
            more = f" и ещё {len(bare) - 3}" if len(bare) > 3 else ""
            result.problems.append(f"{_short(commit)}: без строки журнала изменено {len(bare)}: {', '.join(bare[:3])}{more}; "
                                   "если это сборка — тема коммита `run <N>: …` или `build: …`")
        for row in added:
            files = row_files(row)
            if not files:
                result.problems.append(f"{_short(commit)}: у строки журнала нет поля file")
            elif not any(covers(row, p) for p in commit.paths) and not all(f in ignored for f in files):
                result.problems.append(f"{_short(commit)}: строка журнала про {'; '.join(files)}, а коммит этот файл не меняет")
    return result


def count_minutes(result: Check, rows: Iterable[Mapping[str, str]]) -> Check:
    for row in rows:
        name = row.get("chapter") or "?"
        text = (row.get("person_minutes") or "").strip().replace(",", ".")
        try:
            result.minutes[name] = result.minutes.get(name, 0.0) + float(text)
        except ValueError:
            result.no_minutes[name] = result.no_minutes.get(name, 0) + 1
            result.minutes.setdefault(name, 0.0)
    return result


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *args], capture_output=True, text=True, encoding="utf-8", check=False)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args[:2])}: {done.stderr.strip()[:300]}")
    return done.stdout


def _journal_at(repo: Path, rev: str) -> list[dict[str, str]]:
    done = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{JOURNAL}"], capture_output=True, text=True, encoding="utf-8", check=False)
    return rows_of(done.stdout) if done.returncode == 0 else []


def default_base(repo: Path) -> str:
    """Тег заморозки: последний тег, достижимый из HEAD."""
    done = subprocess.run(["git", "-C", str(repo), "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit("тега заморозки нет: укажите коммит, с которого сверять, — glava journal --base <коммит>")
    return done.stdout.strip()


def history(repo: Path, base: str) -> list[Commit]:
    commits = []
    for sha in _git(repo, "rev-list", "--reverse", "--no-merges", f"{base}..HEAD").split():
        subject = _git(repo, "show", "-s", "--format=%s", sha).strip()
        paths = tuple(p for p in _git(repo, "diff-tree", "--root", "--no-commit-id", "-r", "-z", "--name-only", sha).split("\0") if p)
        added, removed = diff_rows(_journal_at(repo, f"{sha}^"), _journal_at(repo, sha)) if JOURNAL in paths else ([], [])
        commits.append(Commit(sha, subject, paths, tuple(added), tuple(removed)))
    return commits


def _ignored(repo: Path, commits: Sequence[Commit]) -> set[str]:
    """Файлы строк журнала, которых git не хранит (ролики): их правку по истории не сверить."""
    files = sorted({f for c in commits for r in c.added for f in row_files(r)})
    if not files:
        return set()
    done = subprocess.run(["git", "-C", str(repo), "check-ignore", "--no-index", "--stdin"], input="\n".join(files), capture_output=True, text=True, encoding="utf-8", check=False)
    return {line.strip() for line in done.stdout.splitlines() if line.strip()}


def build_journal_check(repo: Path, base: str | None, chapter: str | None = None) -> bool:
    base = base or default_base(repo)
    commits = history(repo, base)
    result = check(commits, chapter, _ignored(repo, commits))
    count_minutes(result, [r for c in commits if not c.is_build for r in c.added if chapter is None or r.get("chapter") == chapter])
    dirty = [p for p in _git(repo, "status", "--porcelain", "-z", "--", "workspace", JOURNAL).split("\0") if p and chapter_of(p[3:])]
    log.info("сверка журнала с git от %s: коммитов %s, из них сборок %s", base, result.commits, sum(c.is_build for c in commits))
    for problem in result.problems:
        log.warning("  %s", problem)
    for name, minutes in sorted(result.minutes.items()):
        missing = result.no_minutes.get(name, 0)
        state = "больше нормы" if minutes > LIMIT_MINUTES else "в норме"
        log.info("  %s: %g чел.-мин (%s, норма до %s)%s", name, minutes, state, LIMIT_MINUTES, f"; без минут строк: {missing}" if missing else "")
    if dirty:
        log.warning("  не закоммичено: %s — сверяется только история", ", ".join(p[3:] for p in dirty[:5]))
    ok = not result.problems and not result.no_minutes
    log.info("журнал совпадает с историей" if ok else "журнал расходится с историей или в нём нет минут")
    return ok
