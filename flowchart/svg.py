"""Render laid-out flowcharts to SVG."""

from __future__ import annotations

from .layout import LGraph, LNode, edge_arrow

FONT = "DejaVu Sans, Segoe UI, Arial, sans-serif"
STROKE = "#000000"
TEXT = "#000000"
EDGE = "#000000"

_FILL = {
    "terminal": "#ffffff",
    "process": "#ffffff",
    "predef": "#ffffff",
    "io": "#ffffff",
    "decision": "#ffffff",
    "hexagon": "#ffffff",
    "connector": "#ffffff",
    "merge": "#f8fafc",
}


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _node_svg(n: LNode, ox: float, oy: float) -> str:
    x, y, w, h = n.x + ox, n.y + oy, n.w, n.h
    fill = _FILL.get(n.kind, "#ffffff")
    parts: list[str] = []
    if n.kind == "terminal":
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{h:.1f}" rx="{h / 2:.1f}" ry="{h / 2:.1f}" fill="{fill}" '
            f'stroke="{STROKE}" stroke-width="1.6"/>'
        )
    elif n.kind == "process":
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{h:.1f}" rx="0" fill="{fill}" '
            f'stroke="{STROKE}" stroke-width="1.6"/>'
        )
    elif n.kind == "predef":
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{h:.1f}" rx="0" fill="{fill}" '
            f'stroke="{STROKE}" stroke-width="1.6"/>'
        )
        for dx in (8.0, w - 8.0):
            parts.append(
                f'<line x1="{x + dx:.1f}" y1="{y:.1f}" '
                f'x2="{x + dx:.1f}" y2="{y + h:.1f}" '
                f'stroke="{STROKE}" stroke-width="1.6"/>'
            )
    elif n.kind == "io":
        sk = 14.0
        pts = f"{x + sk:.1f},{y:.1f} {x + w:.1f},{y:.1f} " \
              f"{x + w - sk:.1f},{y + h:.1f} {x:.1f},{y + h:.1f}"
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{STROKE}" '
            f'stroke-width="1.6"/>'
        )
    elif n.kind == "decision":
        cx = x + w / 2
        cy = y + h / 2
        pts = f"{cx:.1f},{y:.1f} {x + w:.1f},{cy:.1f} " \
              f"{cx:.1f},{y + h:.1f} {x:.1f},{cy:.1f}"
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{STROKE}" '
            f'stroke-width="1.6"/>'
        )
    elif n.kind == "hexagon":
        c = w * 0.16
        pts = f"{x + c:.1f},{y:.1f} {x + w - c:.1f},{y:.1f} " \
              f"{x + w:.1f},{y + h / 2:.1f} {x + w - c:.1f},{y + h:.1f} " \
              f"{x + c:.1f},{y + h:.1f} {x:.1f},{y + h / 2:.1f}"
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{STROKE}" '
            f'stroke-width="1.6"/>'
        )
    elif n.kind == "merge":
        # merge anchors are invisible: only the joining lines are drawn
        return ""
    elif n.kind == "connector":
        parts.append(
            f'<ellipse cx="{x + w / 2:.1f}" cy="{y + h / 2:.1f}" '
            f'rx="{w / 2:.1f}" ry="{h / 2:.1f}" fill="{fill}" '
            f'stroke="{STROKE}" stroke-width="1.6"/>'
        )
    # text lines, vertically centered
    lh = 16.0
    total = len(n.lines) * lh
    ty = y + h / 2 - total / 2 + lh * 0.72
    anchor_x = x + w / 2
    for i, line in enumerate(n.lines):
        parts.append(
            f'<text x="{anchor_x:.1f}" y="{ty + i * lh:.1f}" '
            f'font-family="{FONT}" font-size="12" fill="{TEXT}" '
            f'text-anchor="middle">{_esc(line)}</text>'
        )
    return "".join(parts)


def render_svg(graphs: list[LGraph]) -> str:
    if not graphs:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" '
            'height="80"/>\n'
        )
    pad = 30.0
    hgap = 80.0
    # functions are laid out side by side (main leftmost, subroutines right)
    total_w = pad * 2 + sum(g.width for g in graphs) + hgap * (len(graphs) - 1)
    height = max(g.height for g in graphs) + pad * 2 + 30

    body: list[str] = []
    body.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="' + EDGE + '"/>'
        '</marker></defs>'
    )
    x_off = pad
    oy = pad + 24
    for g in graphs:
        for e in g.edges:
            pts = " ".join(
                f"{px + x_off:.1f},{py + oy:.1f}" for px, py in e.points
            )
            # GOST 19.701-90: arrows only off the default flow direction
            marker = (
                ' marker-end="url(#arrow)"' if edge_arrow(e.points, e.arrow)
                else ""
            )
            body.append(
                f'<polyline points="{pts}" fill="none" stroke="{EDGE}" '
                f'stroke-width="1.6"{marker}/>'
            )
            if e.label:
                body.append(
                    f'<text x="{e.lx + x_off:.1f}" y="{e.ly + oy:.1f}" '
                    f'font-family="{FONT}" font-size="11" fill="#334155" '
                    f'text-anchor="{e.anchor}" stroke="#ffffff" '
                    f'stroke-width="3" paint-order="stroke">'
                    f'{_esc(e.label)}</text>'
                )
        for n in g.nodes:
            body.append(_node_svg(n, x_off, oy))
        x_off += g.width + hgap

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {total_w:.0f} {height:.0f}">\n'
        f'<rect width="100%" height="100%" fill="#f8fafc"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )
