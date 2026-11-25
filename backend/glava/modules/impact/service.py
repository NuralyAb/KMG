"""Живой факт для экрана автора: проба без записи и правка с записью в журнал ручного труда."""

import csv
import json
import threading
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from glava.modules.catalog.api import Repository
from glava.modules.impact.diff import Change, what_if
from glava.modules.impact.files import NotBuilt, look, reach_of
from glava.modules.impact.schemas import FactEdit
from glava.modules.impact.spread import spread
from glava.modules.runs.api import RunManager, RunRecord
from glava.shared.http.errors import conflict, invalid, not_found
from glava.shared.json_files import read, read_or
from glava.shared.paths import REPOSITORY

JOURNAL = ("time", "chapter", "file", "what_changed", "person_minutes", "people", "run_no", "reason")


class Facts:
    def __init__(self, repository: Repository, runs: RunManager) -> None:
        self._repository = repository
        self._runs = runs
        self._lock = threading.Lock()

    @property
    def _root(self) -> Path:
        return self._repository.root

    def pending(self, chapter_id: str) -> dict[str, Any]:
        """Правки слоя, которые ещё не дошли до курса."""
        try:
            return look(self._root, chapter_id, self._layer(chapter_id))[1]
        except NotBuilt as error:
            raise conflict("Курс ещё не собирали: сравнивать не с чем") from error

    def probe(self, chapter_id: str, claim_id: str, text: str) -> dict[str, Any]:
        layer = self._layer(chapter_id)
        node, claim = self._claim(layer, claim_id)
        change = what_if(claim, node["id"], text.strip())
        if change.before == change.after:
            raise invalid("Текст утверждения не изменился")
        tasks = read_or(self._work(chapter_id) / "tasks.json", {"tasks": []})["tasks"]
        _, _, replaced, broken = spread(layer, tasks, [change])
        return {"chapter": chapter_id, "changes": [change.to_json()], "fields": {}, **reach_of(self._root, chapter_id, layer, [change], {}),
                "replaced": replaced, "tasks_hidden": broken}

    def apply(self, chapter_id: str, edit: FactEdit) -> RunRecord:
        """Пишет одно утверждение и запускает пересборку. Дальше — обычный запуск, его видно в журнале."""
        with self._lock:
            self._runs.check_free(chapter_id)
            path = self._work(chapter_id) / "layer.json"
            layer = self._layer(chapter_id)
            node, claim = self._claim(layer, edit.claim_id)
            change = what_if(claim, node["id"], edit.text.strip())
            if change.before == change.after:
                raise invalid("Текст утверждения не изменился")
            if change.is_serious and not edit.accept:
                raise conflict("Правка противоречит цитате автора. Подтвердите, что прав человек, или исправьте текст")
            self._write(path, {**layer, "nodes": [self._edited(n, change) for n in layer["nodes"]]})
            self._note(chapter_id, change, edit)
            args = {"accept": True} if edit.accept else {}
            return self._runs.start("fact", chapter_id, ["--apply", *(["--accept"] if edit.accept else [])], args)

    # --- внутреннее ---

    def _work(self, chapter_id: str) -> Path:
        return self._root / "work" / self._repository.chapter(chapter_id).id

    def _layer(self, chapter_id: str) -> dict[str, Any]:
        path = self._work(chapter_id) / "layer.json"
        if not path.exists():
            raise not_found("Слой главы ещё не собран")
        return read(path)

    @staticmethod
    def _claim(layer: Mapping[str, Any], claim_id: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        for node in layer["nodes"]:
            for claim in node["claims"]:
                if claim["id"] == claim_id:
                    return node, claim
        raise not_found("Такого утверждения в слое нет")

    @staticmethod
    def _edited(node: Mapping[str, Any], change: Change) -> dict[str, Any]:
        return {**node, "claims": [{**c, "text": change.after} if c["id"] == change.claim_id else c for c in node["claims"]]}

    @staticmethod
    def _write(path: Path, layer: Mapping[str, Any]) -> None:
        # замена целиком: читающий конвейер не увидит половину файла
        draft = path.with_suffix(".json.tmp")
        draft.write_text(json.dumps(layer, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        draft.replace(path)

    def _note(self, chapter_id: str, change: Change, edit: FactEdit) -> None:
        """Журнал ручного труда заполняется сразу: потом минуты уже не вспомнить."""
        # журнал рядом с репозиторием; у отдельной папки данных он свой
        path = (REPOSITORY if self._root == REPOSITORY / "workspace" else self._root) / "manual_edits.csv"
        is_new = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, lineterminator="\n")
            if is_new:
                writer.writerow(JOURNAL)
            writer.writerow([datetime.now().isoformat(timespec="minutes"), chapter_id, f"workspace/work/{chapter_id}/layer.json",
                             f"{change.claim_id}: «{change.before}» → «{change.after}»", f"{edit.minutes:g}", 1, "", edit.reason])
