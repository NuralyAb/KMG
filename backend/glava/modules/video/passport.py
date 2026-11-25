"""Паспорт ролика по passport.schema.json."""

from collections.abc import Mapping, Sequence
from typing import Any

from glava.modules.video.timeline import Placed


def build_passport(
    spec: Mapping[str, Any], node: Mapping[str, Any], placed: Sequence[Placed], scene_path: str, checklist: Sequence[Mapping[str, str]],
    answers: Mapping[str, tuple[str, str]], audio: Mapping[str, Any],
) -> dict[str, Any]:
    claims = {c["id"]: c for c in node["claims"]}
    used = list(dict.fromkeys(p.beat["claim_id"] for p in placed if p.beat["claim_id"] in claims))
    return {
        "video_id": spec["video_id"], "node_id": spec["node_id"], "format": "9:16" if spec["format"] == "short" else "16:9",
        "node_card": {k: node[k] for k in ("id", "title", "short_title", "difficulty", "pages", "threshold") if k in node},
        "script": [{"t_start": round(p.start, 2), "t_end": round(p.end, 2), "text": p.beat["say"], "claim_id": p.beat["claim_id"],
                    "is_analogy": p.beat["is_analogy"], "on_screen": p.beat["on_screen"]} for p in placed],
        "sources": [{"claim_id": c, "page_or_dataset": f"стр. {claims[c]['page_pdf']}", "quote": claims[c]["quote"]} for c in used],
        "scene_spec": scene_path,
        "frames": [{"t": round(p.start, 2), "class": p.beat["frame_class"], "label": p.beat["label"]} for p in placed],
        "exaggerations": list(spec["exaggerations"]), "prediction_question": spec["prediction_question"], "transfer_question": spec["transfer_question"],
        "data_it_bridge": spec["data_it_bridge"],
        "physics_checklist": [{"item": f"{c['id']}: {c['item']}", "answer": answers.get(c["id"], ("н/п", ""))[0], "note": answers.get(c["id"], ("", ""))[1]}
                              for c in checklist],
        "audio_check": dict(audio), "listen_check": list(spec.get("terms_to_check", [])),
    }
