"""Кисти на cairo, общие для всех сцен."""

from collections.abc import Sequence

import cairo

FONT = "Segoe UI"
Color = str


def rgba(color: Color, alpha: float = 1.0) -> tuple[float, float, float, float]:
    return (int(color[1:3], 16) / 255, int(color[3:5], 16) / 255, int(color[5:7], 16) / 255, alpha)


def fill_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float, color: Color, alpha: float = 1.0, radius: float = 0) -> None:
    ctx.set_source_rgba(*rgba(color, alpha))
    if radius <= 0:
        ctx.rectangle(x, y, w, h)
    else:
        r = min(radius, w / 2, h / 2)
        ctx.new_sub_path()
        ctx.arc(x + w - r, y + r, r, -1.5708, 0)
        ctx.arc(x + w - r, y + h - r, r, 0, 1.5708)
        ctx.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        ctx.arc(x + r, y + r, r, 3.1416, 4.7124)
        ctx.close_path()
    ctx.fill()


def polyline(ctx: cairo.Context, points: Sequence[tuple[float, float]], color: Color, width: float, alpha: float = 1.0, dash: Sequence[float] = ()) -> None:
    if len(points) < 2:
        return
    ctx.set_source_rgba(*rgba(color, alpha))
    ctx.set_line_width(width)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND if not dash else cairo.LINE_CAP_BUTT)
    ctx.set_dash(list(dash))
    ctx.move_to(*points[0])
    for p in points[1:]:
        ctx.line_to(*p)
    ctx.stroke()
    ctx.set_dash([])


def polygon(ctx: cairo.Context, points: Sequence[tuple[float, float]], color: Color, alpha: float = 1.0) -> None:
    ctx.set_source_rgba(*rgba(color, alpha))
    ctx.move_to(*points[0])
    for p in points[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.fill()


def dot(ctx: cairo.Context, x: float, y: float, r: float, color: Color, alpha: float = 1.0) -> None:
    ctx.set_source_rgba(*rgba(color, alpha))
    ctx.arc(x, y, max(r, 0.1), 0, 6.2832)
    ctx.fill()


def arrow(ctx: cairo.Context, x1: float, y1: float, x2: float, y2: float, color: Color, width: float, alpha: float = 1.0) -> None:
    length = max(1e-6, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    head = width * 3
    bx, by = x2 - ux * head, y2 - uy * head
    polyline(ctx, [(x1, y1), (bx, by)], color, width, alpha)
    polygon(ctx, [(x2, y2), (bx - uy * head * 0.6, by + ux * head * 0.6), (bx + uy * head * 0.6, by - ux * head * 0.6)], color, alpha)


def text_size(ctx: cairo.Context, value: str, size: float, bold: bool = False) -> float:
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    return ctx.text_extents(value).x_advance


def text(ctx: cairo.Context, x: float, y: float, value: str, size: float, color: Color, bold: bool = False, anchor: str = "start", alpha: float = 1.0) -> None:
    width = text_size(ctx, value, size, bold)
    shift = {"start": 0.0, "middle": width / 2, "end": width}[anchor]
    ctx.set_source_rgba(*rgba(color, alpha))
    ctx.move_to(x - shift, y)
    ctx.show_text(value)


def wrap(ctx: cairo.Context, value: str, size: float, width: float, bold: bool = False) -> list[str]:
    lines: list[str] = []
    for word in value.split():
        if lines and text_size(ctx, f"{lines[-1]} {word}", size, bold) <= width:
            lines = [*lines[:-1], f"{lines[-1]} {word}"]
        else:
            lines = [*lines, word]
    return lines
