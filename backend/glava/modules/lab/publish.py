"""Кладёт лабораторию рядом с курсом: страница открывается двойным щелчком, сервер и сеть не нужны."""

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).parent / "assets"
ENTRY = '<script src="lab/diagnosis.js"></script>\n'


def publish_lab(out: Path, data: Mapping[str, Any]) -> None:
    shutil.rmtree(out / "lab", ignore_errors=True)
    shutil.copytree(ASSETS, out / "lab", ignore=shutil.ignore_patterns("lab.html"))
    shutil.copyfile(ASSETS / "lab.html", out / "lab.html")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (out / "lab" / "data.js").write_text(f"window.LAB={payload};\n", encoding="utf-8", newline="\n")
    index = out / "index.html"
    page = index.read_text(encoding="utf-8")
    if ENTRY not in page:
        # data.js лаборатории нужен диагнозу у заданий: в нём тексты заблуждений
        index.write_text(page.replace("</body>", f'<script src="lab/data.js"></script>\n{ENTRY}</body>'), encoding="utf-8", newline="\n")
