"""Симуляторы в курсе: сцены из work/<глава>/simulations, источники — только из утверждений слоя."""

import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

NAME = re.compile(r"[a-z0-9_]+")
LABELS = ("реальные данные", "симуляция", "схема")


def _claims(layer: Mapping) -> dict[str, Mapping]:
    return {c["id"]: c for n in layer["nodes"] for c in n["claims"]}


def bound_scene(scene: Mapping, claim_ids: list[str], claims: Mapping[str, Mapping]) -> dict[str, Any]:
    """Источники сцены берутся из слоя: после правки утверждения симулятор покажет новый текст."""
    if not claim_ids:
        raise ValueError(f"симулятор {scene.get('id')}: нет утверждений слоя")
    lost = [c for c in claim_ids if c not in claims]
    if lost:
        raise ValueError(f"симулятор {scene.get('id')}: в слое нет утверждений {', '.join(lost)}")
    if scene.get("provenance") not in LABELS:
        raise ValueError(f"симулятор {scene.get('id')}: метка происхождения не из списка")
    sources = [{"claim": claims[c]["text"], "page": claims[c]["page_pdf"], "claim_id": c} for c in claim_ids]
    fresh = [{"id": c, "text": claims[c]["text"], "quote": claims[c]["quote"], "page": claims[c]["page_pdf"]} for c in claim_ids]
    return {**scene, "sources": sources, **({"claims": fresh} if "claims" in scene else {})}


def publish_simulations(layer: Mapping, config: Path, player: Path, out: Path) -> dict[str, dict[str, Any]]:
    """Кладёт проигрыватель и сцены в курс; возвращает блоки шагов. Нет симуляторов — курс остаётся лёгким."""
    for old in ("simulations.js", "simulations"):
        target = out / old
        shutil.rmtree(target, ignore_errors=True) if target.is_dir() else target.unlink(missing_ok=True)
    shutil.rmtree(out / "assets" / "sim", ignore_errors=True)
    steps = json.loads(config.read_text(encoding="utf-8"))["steps"] if config.exists() else {}
    if not steps:
        return {}
    claims, nodes = _claims(layer), {n["id"] for n in layer["nodes"]}
    unknown = sorted(set(steps) - nodes)
    if unknown:
        raise ValueError(f"симуляторы для неизвестных шагов: {', '.join(unknown)}")
    folder = config.parent / "simulations"
    scenes: dict[str, Any] = {}
    blocks: dict[str, dict[str, Any]] = {}
    for step, entries in steps.items():
        items = []
        for entry in entries:
            name = entry["scene"]
            if not NAME.fullmatch(name):
                raise ValueError(f"недопустимое имя сцены: {name}")
            scene = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
            scenes[name] = {**bound_scene(scene, entry["claims"], claims), "node_id": step}
            poster = folder / f"{name}.webp"
            if poster.exists():
                (out / "simulations").mkdir(parents=True, exist_ok=True)
                shutil.copyfile(poster, out / "simulations" / poster.name)
            items.append({"id": name, "title": scene["title"], "goal": scene.get("goal") or scene["intro"], "label": scene["provenance"],
                          "poster": f"simulations/{poster.name}" if poster.exists() else None})
        blocks[step] = {"interactive": {"kind": "simulation", "params": {"items": items}}}
    shutil.copytree(player, out / "assets" / "sim")
    payload = json.dumps({"scenes": scenes, "thumbs": {}}, ensure_ascii=False).replace("</", "<\\/")
    (out / "simulations.js").write_text(f"globalThis.SIM_SCENES={payload};\n", encoding="utf-8")
    return blocks
