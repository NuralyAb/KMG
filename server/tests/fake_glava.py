"""Подставная команда вместо настоящего конвейера: печатает аргументы и ведёт себя по имени команды.

errata, review и прочие — быстрый успех; layer — код 3; build и course — ждут файл work/release и держат дочерний процесс.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HEARTBEAT = "import sys, time, pathlib\nwhile True:\n    pathlib.Path(sys.argv[1]).write_text(str(time.time()))\n    time.sleep(0.05)\n"


def emit(line: str) -> None:
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def main() -> int:
    command, chapter = sys.argv[1], sys.argv[2]
    emit(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "utf8": os.environ.get("PYTHONUTF8"),
                     "venv": os.environ.get("VIRTUAL_ENV")}, ensure_ascii=False))
    emit(f"этап {command} главы {chapter}")
    if command == "layer":
        emit("узлы не прошли схему")
        return 3
    if command not in ("build", "course"):
        return 0
    work = Path("work")
    work.mkdir(exist_ok=True)
    child = subprocess.Popen([sys.executable, "-c", HEARTBEAT, str(work / f"beat_{chapter}")])
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not (work / "release").exists():
            time.sleep(0.05)
    finally:
        child.kill()
        child.wait()
    emit("готово")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
