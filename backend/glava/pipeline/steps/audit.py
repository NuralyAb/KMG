"""audit: бесплатная сверка слоя кодом."""

import logging
from typing import Any

from glava.modules.trust.api import audit_layer, measure
from glava.pipeline.chapter import file_digest, layer_of
from glava.shared.json_files import save

log = logging.getLogger("glava")


def build_audit(chapter_id: str) -> dict[str, Any]:
    """Бесплатно: сверка слоя кодом и замер, насколько эта сверка чутка."""
    work, layer = layer_of(chapter_id)
    claims = [c for n in layer["nodes"] for c in n["claims"]]
    report = {**audit_layer(layer), "sensitivity": measure(claims), "layer_sha256": file_digest(work / "layer.json")}
    save(work / "audit.json", report)
    sense = report["sensitivity"]
    log.info("утверждений %s, с расхождениями %s %s; терминов раньше объяснения %s; порчи поймано %s из %s", report["claims"], len(report["flagged"]),
             report["by_flag"], len(report["early_terms"]), sense["caught"], sense["made"])
    return report
