"""Готовит данные «Слепой скважины» из открытых LAS Volve. Нужна только стандартная библиотека.

    python scripts/volve_practice.py <папка с LAS> workspace/domain/geology/practice/volve_blind.json

Папка — распакованный spwla_volve (github.com/andymcdgeo/spwla_volve). Сырые кривые берутся из WLC_PETRO_COMPUTED_INPUT,
ответ — из WLC_PETRO_COMPUTED_OUTPUT. Числа не сглаживаются: берётся каждый второй отсчёт (0,2 м).
"""

import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

NULL = -900
MEASURED = ("GR", "RT", "RHOB", "NPHI")
ANSWER = ("VSH", "PHIF", "SW", "SAND_FLAG")
STEP = 2
MATRIX, FLUID = 2.65, 1.0
RW_20, T_RES = 0.07, 111.0  # отчёт скважин F-11: Rw = 0,07 Ом·м при 20 °C, температура пласта 111 °C
WELLS = (
    {"id": "w1", "name": "Скважина 1", "real_name": "15/9-F-11 A", "folder": "15_9-F11A", "top": 3572, "base": 3712, "intervals": (
        ("w1a", 3576.0, 3583.0, "shale"), ("w1b", 3613.5, 3617.5, "oil"), ("w1c", 3636.0, 3640.0, "oil"), ("w1d", 3660.0, 3661.6, "tight"), ("w1e", 3677.0, 3683.0, "oil"))},
    {"id": "w2", "name": "Скважина 2", "real_name": "15/9-F-11 T2", "folder": "15_9-F11 T2", "top": 4352, "base": 4500, "intervals": (
        ("w2a", 4355.0, 4365.0, "shale"), ("w2b", 4394.0, 4398.0, "residual"), ("w2c", 4407.5, 4411.0, "water"), ("w2d", 4446.2, 4448.8, "tight"), ("w2e", 4466.0, 4472.0, "water"),
        ("w2f", 4490.0, 4494.0, "water"))},
)


def read_las(path: Path) -> tuple[list[str], list[list[float]]]:
    text = path.read_text(encoding="latin-1")
    start = re.search(r"^~A.*$", text, re.MULTILINE)
    if start is None:
        raise SystemExit(f"{path.name}: нет раздела данных")
    section, names = "", []
    for line in text[:start.start()].splitlines():
        if line.startswith("~"):
            section = line[1:2].upper()
        elif section == "C" and line.strip() and not line.startswith("#"):
            names.append(line.split(".", 1)[0].strip())
    numbers = [float(x) for x in text[start.end():].split()]
    return names, [numbers[i:i + len(names)] for i in range(0, len(numbers) - len(names) + 1, len(names))]


def curve(names: list[str], rows: list[list[float]], name: str) -> dict[float, float]:
    at = names.index(name)
    return {round(r[0], 1): r[at] for r in rows if r[at] > NULL}


def resistivity_of_water() -> float:
    """Пересчёт Rw на температуру пласта по формуле Арпса."""
    return RW_20 * (20 + 21.5) / (T_RES + 21.5)


def medians(well: dict[str, Any], top: float, base: float) -> dict[str, float]:
    inside = [i for i, z in enumerate(well["depth"]) if top <= z <= base]
    found = {}
    for name, values in {**well["curves"], **well["answer"]}.items():
        kept = [values[i] for i in inside if values[i] is not None]
        if kept:
            found[name] = round(statistics.median(kept), 3)
    return found


def expected(m: dict[str, float]) -> str:
    """Класс по интерпретации оператора: те же пороги песчаника, что в отчёте (PHIF > 0,10, VSH < 0,50)."""
    if m["VSH"] >= 0.5:
        return "shale"
    if m.get("PHIF", 0) <= 0.10 or m["SAND_FLAG"] < 0.5:
        return "tight"
    return "oil" if m["SW"] < 0.5 else "water"


def build_well(folder: Path, spec: dict[str, Any]) -> dict[str, Any]:
    where = next((p for p in (folder / spec["folder"], folder) if list(p.glob("*COMPUTED_INPUT*"))), None)
    if where is None:
        raise SystemExit(f"нет LAS для {spec['real_name']}")
    raw, done = (read_las(next(where.glob(f"*COMPUTED_{kind}_1.LAS"))) for kind in ("INPUT", "OUTPUT"))
    tracks = {n: curve(*raw, n) for n in MEASURED}
    answers = {n: curve(*done, n) for n in ANSWER}
    depth = [round(spec["top"] + i * 0.1 * STEP, 1) for i in range(int((spec["base"] - spec["top"]) / (0.1 * STEP)) + 1)]
    well = {"id": spec["id"], "name": spec["name"], "real_name": spec["real_name"], "depth": depth,
            "curves": {n: [round(t[z], 3) if z in t else None for z in depth] for n, t in tracks.items()},
            "answer": {n: [round(t[z], 3) if z in t else None for z in depth] for n, t in answers.items()}, "intervals": []}
    for key, top, base, truth in spec["intervals"]:
        m = medians(well, top, base)
        got = expected(m)
        if got != truth and truth != "residual":
            raise SystemExit(f"{key}: в таблице {truth}, по данным {got} {m}")
        phi = (MATRIX - m["RHOB"]) / (MATRIX - FLUID)
        rho_w = resistivity_of_water() / phi ** 2 if phi > 0.02 else None
        well["intervals"].append({"id": key, "top": top, "base": base, "truth": truth, "medians": m, "porosity_density": round(phi, 3),
                                  "pn": round(m["RT"] / rho_w, 1) if rho_w else None})
    return well


def main() -> None:
    folder, target = Path(sys.argv[1]), Path(sys.argv[2])
    spec = json.loads(target.with_name("volve_blind.texts.json").read_text(encoding="utf-8"))
    data = {**spec, "rw": round(resistivity_of_water(), 4), "wells": [build_well(folder, w) for w in WELLS]}
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    for w in data["wells"]:
        for i in w["intervals"]:
            print(i["id"], i["truth"], i["medians"], "phi", i["porosity_density"], "Pn", i["pn"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
