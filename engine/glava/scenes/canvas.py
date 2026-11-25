"""Мелочи рисования. Ширина 480 выбрана так, чтобы на телефоне 390 px шрифт оставался не мельче 16 px."""

from collections.abc import Sequence
from xml.sax.saxutils import escape, quoteattr

W = 480
PAD = 20
FONT = 22
LINE = 28
CHAR = 12.0


def text_width(value: str) -> float:
    return len(value) * CHAR


def _split_long(word: str, limit: int) -> list[str]:
    if len(word) <= limit:
        return [word]
    return [word[: limit - 1] + "-", *_split_long(word[limit - 1:], limit)]


def wrap(value: str, width: float) -> list[str]:
    limit = max(4, int(width // CHAR))
    lines: list[str] = []
    for word in (part for w in value.split() for part in _split_long(w, limit)):
        if lines and len(lines[-1]) + 1 + len(word) <= limit:
            lines = [*lines[:-1], f"{lines[-1]} {word}"]
        else:
            lines = [*lines, word]
    return lines


def text(x: float, y: float, value: str, color: str, anchor: str = "start", weight: int = 400) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="{FONT}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'


def lines(x: float, y: float, values: Sequence[str], color: str, anchor: str = "start", weight: int = 400) -> str:
    return "".join(text(x, y + i * LINE, v, color, anchor, weight) for i, v in enumerate(values))


def rect(x: float, y: float, w: float, h: float, fill: str, radius: float = 0, stroke: str = "none", extra: str = "") -> str:
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" rx="{radius}" fill={quoteattr(fill)} '
            f'stroke={quoteattr(stroke)} {extra}/>')


def line(x1: float, y1: float, x2: float, y2: float, color: str, width: float = 2, dash: str = "") -> str:
    dashed = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{dashed}/>'


def path(points: Sequence[tuple[float, float]], color: str, width: float = 3, fill: str = "none", closed: bool = False, extra: str = "") -> str:
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + (" Z" if closed else "")
    return f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" {extra}/>'


def arrow(x1: float, y1: float, x2: float, y2: float, color: str, width: float = 3, size: float = 9) -> str:
    """Линия со стрелкой на конце."""
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / length, dy / length
    bx, by = x2 - ux * size * 1.4, y2 - uy * size * 1.4
    head = [(x2, y2), (bx - uy * size, by + ux * size), (bx + uy * size, by - ux * size)]
    return line(x1, y1, bx, by, color, width) + path(head, color, 1, fill=color, closed=True)


def legend(items: Sequence[tuple[str, str]], y: float, color: str) -> tuple[str, float]:
    """Подписи цветов столбиком; возвращает рисунок и нижнюю границу."""
    out = ""
    for swatch, name in items:
        rows = wrap(name, W - 2 * PAD - 34)
        out += rect(PAD, y + 4, 22, 22, swatch, radius=4, stroke="#ECEFF4") + lines(PAD + 34, y + 22, rows, color)
        y += LINE * len(rows) + 6
    return out, y
