"""Сводка ответа модуля проверки против ключа: только цифры, без текста ключа.

Запуск: python scripts/review_compare.py <ответ.json> <key.json>

Считает так же, как жюри (первое замечание на цель, полный зачёт — верная страница и непустой fix),
и раскладывает находки, пропуски и ложные тревоги по категориям и типам целей.
Печатает только числа и id целей: содержимое ключа в репозиторий не попадает.
"""

import json
import sys
from collections import Counter

W = {"critical": 3, "significant": 2, "minor": 1}


def kind(target: str) -> str:
    return {"C": "claim", "A": "analogy", "L": "script_line", "S": "scene_fact", "F": "frame"}.get(target[:1], "other")


def compare(answer: dict, key: dict) -> dict:
    errors = {e["target"]: e for e in key["errors"]}
    tricky = {t["target"] for t in key["tricky_true"]}
    seen: set[str] = set()
    first = []
    for remark in answer.get("remarks", []):
        if remark.get("target") not in seen:
            seen.add(remark.get("target"))
            first.append(remark)
    full, half, false, false_tricky, got = [], [], [], [], 0.0
    same_category = 0
    for remark in first:
        error = errors.get(remark["target"])
        if error is None:
            false.append(remark)
            if remark["target"] in tricky:
                false_tricky.append(remark)
            continue
        same_category += remark.get("category") == error["category"]
        if remark.get("page_pdf") in error["pages"] and str(remark.get("fix") or "").strip():
            full.append(error)
            got += W[error["severity"]]
        else:
            half.append(error)
            got += W[error["severity"]] / 2
    found = {e["target"] for e in (*full, *half)}
    missed = [e for t, e in errors.items() if t not in found]
    total = sum(W[e["severity"]] for e in errors.values())
    by_category = {c: {"всего": n, "найдено": sum(e["category"] == c for e in (*full, *half)),
                       "полностью": sum(e["category"] == c for e in full)}
                   for c, n in sorted(Counter(e["category"] for e in errors.values()).items())}
    return {
        "ошибок": len(errors), "вес": total, "верных_неожиданных": len(tricky), "замечаний": len(first),
        "полностью": len(full), "наполовину": len(half), "пропущено": len(missed),
        "ложных": len(false), "ложных_на_неожиданных": len(false_tricky),
        "доля_по_весу": round(got / total, 3) if total else 0.0, "категория_совпала": same_category,
        "по_категориям_ключа": by_category,
        "пропуски_по_типу_цели": dict(Counter(kind(e["target"]) for e in missed)),
        "пропуски_по_тяжести": dict(Counter(e["severity"] for e in missed)),
        "ложные_по_типу_цели": dict(Counter(kind(r["target"]) for r in false)),
        "ложные_по_нашей_категории": dict(Counter(r.get("category") for r in false)),
        "пропущены_id": sorted(e["target"] for e in missed),
        "ложные_id": sorted(r["target"] for r in false),
        "наполовину_id": sorted(e["target"] for e in half),
    }


def main(answer_path: str, key_path: str) -> None:
    answer = json.load(open(answer_path, encoding="utf-8"))
    key = json.load(open(key_path, encoding="utf-8"))
    print(json.dumps(compare(answer, key), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
