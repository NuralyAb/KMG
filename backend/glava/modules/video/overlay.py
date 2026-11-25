"""Слой поверх сцены: ключевые слова, метка происхождения, плашка честности, пауза на предсказание, карта шагов."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import cairo

from glava.modules.video.draw import dot, fill_rect, text, text_size, wrap
from glava.modules.video.timeline import Placed, current

FADE = 0.25
KINDS = {"observation": "наблюдение", "inference": "вывод", "assumption": "допущение"}


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    top: int
    bottom: int
    side: int
    caption: int
    small: int

    @property
    def scene(self) -> tuple[float, float, float, float]:
        """Прямоугольник сцены между подписью сверху и плашкой снизу."""
        head = self.caption * 2.9
        return self.side, self.top + head, self.width - 2 * self.side, self.height - self.top - self.bottom - head - self.small * 2.6


SHORT = Layout(1080, 1920, 220, 380, 70, 58, 44)
WIDE = Layout(1920, 1080, 60, 70, 80, 52, 36)
LAYOUTS = {"short": SHORT, "wide": WIDE}


def draw_overlay(ctx: cairo.Context, t: float, placed: Sequence[Placed], spec: Mapping[str, Any], style: Mapping[str, Any], layout: Layout) -> None:
    item = current(t, placed)
    alpha = min(1.0, max(0.0, (t - item.start) / FADE)) if item is not placed[0] else 1.0
    _caption(ctx, item.beat, style, layout, alpha)
    _badge(ctx, item.beat["label"], style, layout)
    _kind(ctx, item.beat, spec.get("claim_kinds") or {}, style, layout)
    notes = [*spec["plaque"], *([style["school"]] if item.beat["frame_class"] == "A" and style.get("school") else [])]
    _plaque(ctx, notes[placed.index(item) % len(notes)], style, layout)
    _steps(ctx, t, placed, style, layout)
    if item.beat["role"] == "prediction" and t > item.end:
        _guess(ctx, spec["prediction_question"], style, layout)


def _caption(ctx: cairo.Context, beat: Mapping[str, Any], style: Mapping[str, Any], layout: Layout, alpha: float) -> None:
    rows = wrap(ctx, beat["on_screen"], layout.caption, layout.width - 2 * layout.side, True)[:2]
    y = layout.top + layout.caption
    for row in rows:
        text(ctx, layout.width / 2, y, row, layout.caption, style["text"], True, "middle", alpha)
        y += layout.caption * 1.2
    if beat["is_analogy"]:
        text(ctx, layout.width / 2, y, "аналогия", layout.small, style["muted"], False, "middle", alpha)


def _badge(ctx: cairo.Context, label: str, style: Mapping[str, Any], layout: Layout) -> None:
    width = text_size(ctx, label, layout.small, True) + layout.small
    y = layout.height - layout.bottom - layout.small * 1.6
    fill_rect(ctx, layout.side, y, width, layout.small * 1.6, style["provenance"][label], radius=10)
    text(ctx, layout.side + width / 2, y + layout.small * 1.15, label, layout.small, "#FFFFFF", True, "middle")


def _kind(ctx: cairo.Context, beat: Mapping[str, Any], kinds: Mapping[str, str], style: Mapping[str, Any], layout: Layout) -> None:
    """Наблюдение, вывод или допущение: зритель видит, что измерено, а что из этого следует."""
    word = "аналогия" if beat["is_analogy"] else KINDS.get(kinds.get(beat["claim_id"] or "", ""))
    if not word:
        return
    x = layout.side + text_size(ctx, beat["label"], layout.small, True) + layout.small * 1.4
    y = layout.height - layout.bottom - layout.small * 1.6
    width = text_size(ctx, word, layout.small, True) + layout.small
    fill_rect(ctx, x, y, width, layout.small * 1.6, style["panel"], radius=10)
    text(ctx, x + width / 2, y + layout.small * 1.15, word, layout.small, style["text"], True, "middle")


def _plaque(ctx: cairo.Context, plaque: str, style: Mapping[str, Any], layout: Layout) -> None:
    """Плашка честности строкой под метками: места хватает и длинной оговорке."""
    size = float(layout.small)
    while size > layout.small * 0.6 and text_size(ctx, plaque, size) > layout.width - 2 * layout.side:
        size -= 1
    text(ctx, layout.side, layout.height - layout.bottom + layout.small * 1.1, plaque, size, style["muted"])


def _steps(ctx: cairo.Context, t: float, placed: Sequence[Placed], style: Mapping[str, Any], layout: Layout) -> None:
    gap = (layout.width - 2 * layout.side) / len(placed)
    y = layout.top - layout.small * 0.5
    for i, item in enumerate(placed):
        done = t >= item.start
        fill_rect(ctx, layout.side + i * gap + 3, y, gap - 6, 6, style["text"] if done else style["panel"], 0.9 if done else 1.0, 3)


def _guess(ctx: cairo.Context, question: str, style: Mapping[str, Any], layout: Layout) -> None:
    x, y, w, h = layout.scene
    rows = wrap(ctx, question, layout.caption, w * 0.8, True)
    height = len(rows) * layout.caption * 1.25 + layout.caption * 1.6
    top = y + h * 0.5 - height / 2
    fill_rect(ctx, x + w * 0.05, top, w * 0.9, height, style["panel"], 0.96, 24)
    for i, row in enumerate(rows):
        text(ctx, x + w / 2, top + layout.caption * (1.5 + i * 1.25), row, layout.caption, style["text"], True, "middle")
    for k in range(3):
        dot(ctx, x + w / 2 + (k - 1) * 40, top + height - layout.caption * 0.4, 8, style["measurement"]["color"])
