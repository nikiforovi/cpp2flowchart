"""Export laid-out flowcharts to draw.io (diagrams.net) XML.

One page (diagram tab) per function. Blocks become native draw.io shapes,
edges keep the exact orthogonal route of the layout (waypoints + fixed
exit/entry ports) and stay attached to their blocks, so the chart can be
edited in draw.io without falling apart. Invisible merge anchors are not
exported as cells: lines simply start/end at the junction point.
"""

from __future__ import annotations

import html
import math
import xml.etree.ElementTree as ET

from .layout import LEdge, LGraph, LNode, edge_arrow
from .svg import EDGE, STROKE, TEXT, _FILL

MARGIN = 20.0       # page margin around a chart
LABEL_FONT = 11
LABEL_CHAR_W = 6.2  # approx char width of an edge label

_SHAPE = {
    "terminal": "rounded=1;arcSize=50;",
    "process": "rounded=0;",
    "io": "shape=parallelogram;perimeter=parallelogramPerimeter;"
          "fixedSize=1;size=14;",
    "decision": "rhombus;",
}


def _node_style(n: LNode) -> str:
    if n.kind == "predef":
        shape = (f"shape=process;backgroundOutline=1;"
                 f"size={8.0 / max(n.w, 1.0):.4f};")
    elif n.kind == "hexagon":
        # same bevel as the SVG renderer: 16% of the width
        shape = (f"shape=hexagon;perimeter=hexagonPerimeter2;fixedSize=1;"
                 f"size={n.w * 0.16:.1f};")
    else:
        shape = _SHAPE.get(n.kind, "rounded=0;")
    fill = _FILL.get(n.kind, "#ffffff")
    return (f"{shape}whiteSpace=wrap;html=1;fillColor={fill};"
            f"strokeColor={STROKE};strokeWidth=1.6;fontColor={TEXT};"
            f"fontSize=12;")


def _node_value(n: LNode) -> str:
    # lines are already wrapped by the layout: keep the same breaks
    return "<br>".join(html.escape(line, quote=False) for line in n.lines)


def _fraction(n: LNode, pt: tuple[float, float]) -> tuple[float, float]:
    """Port position of `pt` on `n` as draw.io relative constraint."""
    fx = (pt[0] - n.x) / n.w if n.w else 0.5
    fy = (pt[1] - n.y) / n.h if n.h else 0.5
    return (round(min(max(fx, 0.0), 1.0), 4),
            round(min(max(fy, 0.0), 1.0), 4))


def _label_geometry(e: LEdge) -> tuple[float, float, float]:
    """(relative x along the edge in -1..1, offset dx, offset dy).

    The layout gives the label anchor (lx, ly, text-anchor) in SVG terms;
    draw.io centres a label on a point of the edge plus an offset.
    """
    tw = len(e.label) * LABEL_CHAR_W
    cx = e.lx + (tw / 2 if e.anchor == "start"
                 else -tw / 2 if e.anchor == "end" else 0.0)
    cy = e.ly - LABEL_FONT * 0.35  # baseline -> visual centre
    pts = e.points
    total = sum(math.dist(p, q) for p, q in zip(pts, pts[1:]))
    if total <= 0:
        return 0.0, cx - pts[0][0], cy - pts[0][1]
    best = (math.inf, 0.0, pts[0])
    run = 0.0
    for p, q in zip(pts, pts[1:]):
        seg = math.dist(p, q)
        if seg > 0:
            t = ((cx - p[0]) * (q[0] - p[0]) + (cy - p[1]) * (q[1] - p[1])) \
                / (seg * seg)
            t = min(max(t, 0.0), 1.0)
            proj = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
            d = math.dist(proj, (cx, cy))
            if d < best[0]:
                best = (d, run + t * seg, proj)
        run += seg
    _, along, proj = best
    return 2 * along / total - 1, cx - proj[0], cy - proj[1]


def _pt(parent: ET.Element, x: float, y: float, role: str | None = None):
    attrs = {"x": f"{x:.1f}", "y": f"{y:.1f}"}
    if role:
        attrs["as"] = role
    return ET.SubElement(parent, "mxPoint", attrs)


def _page(g: LGraph, index: int) -> ET.Element:
    ox = oy = MARGIN
    diagram = ET.Element("diagram", {"id": f"c2fc-{index}", "name": g.name})
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "0", "dy": "0", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1",
        "pageWidth": f"{g.width + 2 * MARGIN:.0f}",
        "pageHeight": f"{g.height + 2 * MARGIN:.0f}",
        "math": "0", "shadow": "0",
    })
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    nodes = {n.id: n for n in g.nodes}
    visible = {n.id for n in g.nodes if n.kind != "merge"}
    for n in g.nodes:
        if n.id not in visible:
            continue
        cell = ET.SubElement(root, "mxCell", {
            "id": f"n{n.id}", "value": _node_value(n),
            "style": _node_style(n), "vertex": "1", "parent": "1",
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": f"{n.x + ox:.1f}", "y": f"{n.y + oy:.1f}",
            "width": f"{n.w:.1f}", "height": f"{n.h:.1f}",
            "as": "geometry",
        })

    for i, e in enumerate(g.edges):
        if len(e.points) < 2:
            continue
        arrow = edge_arrow(e.points, e.arrow)
        style = (f"edgeStyle=none;rounded=0;html=1;strokeColor={EDGE};"
                 f"strokeWidth=1.6;endArrow={'block' if arrow else 'none'};"
                 f"endFill=1;startArrow=none;")
        attrs = {"id": f"e{i}", "value": "", "style": "", "edge": "1",
                 "parent": "1"}
        if e.src in visible:
            attrs["source"] = f"n{e.src}"
            fx, fy = _fraction(nodes[e.src], e.points[0])
            style += f"exitX={fx};exitY={fy};exitDx=0;exitDy=0;"
        if e.dst in visible:
            attrs["target"] = f"n{e.dst}"
            fx, fy = _fraction(nodes[e.dst], e.points[-1])
            style += f"entryX={fx};entryY={fy};entryDx=0;entryDy=0;"
        attrs["style"] = style
        cell = ET.SubElement(root, "mxCell", attrs)
        geo = ET.SubElement(cell, "mxGeometry",
                            {"relative": "1", "as": "geometry"})
        (sx, sy), (tx, ty) = e.points[0], e.points[-1]
        _pt(geo, sx + ox, sy + oy, "sourcePoint")
        _pt(geo, tx + ox, ty + oy, "targetPoint")
        if len(e.points) > 2:
            arr = ET.SubElement(geo, "Array", {"as": "points"})
            for px, py in e.points[1:-1]:
                _pt(arr, px + ox, py + oy)
        if e.label:
            rel, dx, dy = _label_geometry(e)
            lbl = ET.SubElement(root, "mxCell", {
                "id": f"e{i}-label", "value": html.escape(e.label,
                                                          quote=False),
                "style": (f"edgeLabel;html=1;align=center;"
                          f"verticalAlign=middle;resizable=0;points=[];"
                          f"labelBackgroundColor=#ffffff;"
                          f"fontSize={LABEL_FONT};fontColor=#334155;"),
                "vertex": "1", "connectable": "0", "parent": f"e{i}",
            })
            lgeo = ET.SubElement(lbl, "mxGeometry", {
                "x": f"{rel:.4f}", "relative": "1", "as": "geometry",
            })
            _pt(lgeo, dx, dy, "offset")
    return diagram


def render_drawio(graphs: list[LGraph]) -> str:
    """Render flowcharts as a draw.io document (one page per function)."""
    mxfile = ET.Element("mxfile", {"host": "c2fc", "type": "device"})
    for i, g in enumerate(graphs):
        mxfile.append(_page(g, i))
    if not graphs:
        empty = ET.SubElement(mxfile, "diagram",
                              {"id": "c2fc-0", "name": "empty"})
        model = ET.SubElement(empty, "mxGraphModel")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    ET.indent(mxfile, space="  ")
    return (ET.tostring(mxfile, encoding="unicode", xml_declaration=False)
            + "\n")
