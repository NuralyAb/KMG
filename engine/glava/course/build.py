"""Сборка демо-курса: слой + маршруты + задания + иллюстрации -> папка с HTML, которая открывается без сервера."""

import json
import re
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).parent / "assets"
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«\d$(])")
WORD = re.compile(r"[а-яёa-z]{4,}", re.IGNORECASE)
SENTENCES_PER_PARAGRAPH = 3
WORDS_PER_MINUTE = 130
MIN_MINUTES = 2
MIN_OVERLAP = 2
STEM = 6
HOW_BLOCKS = (("mechanism", "Механизм"), ("practice", "Как работает специалист"), ("nuances", "Нюансы"))

INDEX = """<!doctype html>
<html lang="ru" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="assets/katex/katex.min.css">
<link rel="stylesheet" href="assets/course.css">
</head>
<body>
<a class="skip" href="#main">К содержанию</a>
<div id="app"></div>
<noscript>Для курса нужен JavaScript.</noscript>
<script src="assets/katex/katex.min.js"></script>
<script src="data.js"></script>
<script src="assets/course.js"></script>
</body>
</html>
"""


def paragraphs(text: str) -> list[str]:
    sentences = SENTENCE.split(text.strip())
    size = SENTENCES_PER_PARAGRAPH
    return [" ".join(sentences[i:i + size]) for i in range(0, len(sentences), size)]


def _stems(text: str) -> set[str]:
    return {w.casefold()[:STEM] for w in WORD.findall(text)}


def source_pages(text: str, claims: Sequence[Mapping], fallback: Sequence[int]) -> list[int]:
    """Страницы абзаца — страницы утверждений, с которыми у него больше всего общих слов."""
    words = _stems(text)
    scored = [(len(words & _stems(c["text"])), c["page_pdf"]) for c in claims]
    best = max((s for s, _ in scored), default=0)
    if best < MIN_OVERLAP:
        return sorted(fallback)
    return sorted({page for score, page in scored if score >= max(MIN_OVERLAP, best * 0.75)})


def reading_minutes(node: Mapping) -> int:
    words = sum(len(v["text"].split()) for k, v in node["layers"].items() if k != "deeper")
    words += sum(len(c["text"].split()) for c in node["claims"]) // 2
    return max(MIN_MINUTES, round(words / WORDS_PER_MINUTE))


def _with_pages(text: str, node: Mapping) -> list[dict[str, Any]]:
    return [{"text": p, "pages": source_pages(p, node["claims"], node["pages"])} for p in paragraphs(text)]


def step_data(node: Mapping, route: Mapping | None, tasks: Sequence[Mapping], pictures: Sequence[Mapping]) -> dict[str, Any]:
    layers = node["layers"]
    how = [{"title": title, "by_model": layers[key]["by_model"], "paragraphs": _with_pages(layers[key]["text"], node)}
           for key, title in HOW_BLOCKS if layers[key]["text"].strip()]
    deeper = [{"text": d["text"], "pages": source_pages(d["text"], node["claims"], node["pages"])} for d in layers.get("deeper", [])]
    kept = ("title", "short_title", "why_here", "difficulty", "threshold", "pages", "misconception", "data_meaning", "it_analogy", "now_practice",
            "inefficiency_lens", "decision_on_data", "worked_examples", "book_tasks", "terms_introduced", "links", "needs_scan", "claims")
    return {
        **{k: node.get(k) for k in kept}, "id": node["id"], "order": node["order"], "minutes": reading_minutes(node),
        "essence": layers["main"]["text"], "how": how, "deeper": deeper, "glossary": node.get("glossary", []),
        "format": (route or {}).get("format"), "tasks": [t for t in tasks if t["step_id"] == node["id"]],
        "pictures": [p for p in pictures if p["step_id"] == node["id"]],
    }


def course_data(layer: Mapping, routing: Mapping, tasks: Sequence[Mapping], pictures: Sequence[Mapping]) -> dict[str, Any]:
    routes = {r["node_id"]: r for r in routing["routes"]}
    ordered = sorted(layer["nodes"], key=lambda n: n["order"])
    return {
        "id": layer["chapter"], "title": layer["title"], "book": layer["book"], "generated_by": layer["generated_by"], "parts": layer["parts"],
        "steps": [step_data(n, routes.get(n["id"]), tasks, pictures) for n in ordered],
    }


def build_course(
    layer: Mapping, routing: Mapping, tasks: Sequence[Mapping], pictures: Sequence[Mapping], out: Path, picture_files: Path | None = None,
) -> Path:
    data = course_data(layer, routing, tasks, pictures)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ASSETS, out / "assets", dirs_exist_ok=True)
    if picture_files and picture_files.exists():
        shutil.copytree(picture_files, out / "pictures", dirs_exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (out / "data.js").write_text(f"window.COURSE={payload};\n", encoding="utf-8")
    title = data["title"].replace("&", "&amp;").replace("<", "&lt;")
    (out / "index.html").write_text(INDEX.format(title=title), encoding="utf-8")
    return out
