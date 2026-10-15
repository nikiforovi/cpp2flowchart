"""Geometry sanity checks for laid-out flowcharts (used by tests).

* an edge segment must not run through the interior of a block other than
  the edge's own source / target (merge anchors are invisible: ignored);
* two different edges must not run on top of each other (collinear
  overlap), except the short stretch where lines join into the same
  target (a GOST junction).
"""

from __future__ import annotations

from flowchart.layout import LGraph, LNode

EPS = 0.5


def _segs(pts):
    return list(zip(pts, pts[1:]))


def _seg_hits_node(p, q, n: LNode, margin: float = 1.0) -> bool:
    (x0, y0), (x1, y1) = p, q
    lx, hx = min(x0, x1), max(x0, x1)
    ly, hy = min(y0, y1), max(y0, y1)
    return (lx < n.x + n.w - margin and hx > n.x + margin
            and ly < n.y + n.h - margin and hy > n.y + margin)


def _through_point(p, q, pt) -> bool:
    (x0, y0), (x1, y1) = p, q
    if abs(x0 - x1) < EPS:
        return abs(pt[0] - x0) < EPS and \
            min(y0, y1) + EPS < pt[1] < max(y0, y1) - EPS
    return abs(pt[1] - y0) < EPS and \
        min(x0, x1) + EPS < pt[0] < max(x0, x1) - EPS


def _parallel(s, t, near: float = 4.0) -> tuple[float, float]:
    """(offset, overlap) of two parallel axis-aligned segments within `near`."""
    (a0, a1), (b0, b1) = s, t
    av, bv = abs(a0[0] - a1[0]) < EPS, abs(b0[0] - b1[0]) < EPS
    if av != bv:
        return -1.0, 0.0
    k, o = (0, 1) if av else (1, 0)
    off = abs(a0[k] - b0[k])
    if off >= near:
        return -1.0, 0.0
    lo = max(min(a0[o], a1[o]), min(b0[o], b1[o]))
    hi = min(max(a0[o], a1[o]), max(b0[o], b1[o]))
    return off, max(0.0, hi - lo)


def _collinear_overlap(s, t) -> float:
    (a0, a1), (b0, b1) = s, t
    if abs(a0[0] - a1[0]) < EPS and abs(b0[0] - b1[0]) < EPS \
            and abs(a0[0] - b0[0]) < EPS:
        lo = max(min(a0[1], a1[1]), min(b0[1], b1[1]))
        hi = min(max(a0[1], a1[1]), max(b0[1], b1[1]))
        return max(0.0, hi - lo)
    if abs(a0[1] - a1[1]) < EPS and abs(b0[1] - b1[1]) < EPS \
            and abs(a0[1] - b0[1]) < EPS:
        lo = max(min(a0[0], a1[0]), min(b0[0], b1[0]))
        hi = min(max(a0[0], a1[0]), max(b0[0], b1[0]))
        return max(0.0, hi - lo)
    return 0.0


def node_hits(g: LGraph) -> list[str]:
    """Edge segments passing through foreign blocks."""
    out = []
    for i, e in enumerate(g.edges):
        own = {e.src, e.dst}
        for p, q in _segs(e.points):
            for n in g.nodes:
                if n.id in own:
                    continue
                if n.kind == "merge":
                    if _through_point(p, q, (n.x, n.y)):
                        out.append(f"{g.name}: E{i} {p}->{q} runs through "
                                   f"junction N{n.id}")
                    continue
                if _seg_hits_node(p, q, n):
                    out.append(f"{g.name}: E{i} {p}->{q} crosses N{n.id} "
                               f"{n.lines}")
    return out


def edge_overlaps(g: LGraph) -> list[str]:
    """Lines running on top of each other (or hugging within 4px).

    Exactly collinear stretches are fine only between edges that join
    (same target) or fan out (same start point, e.g. a switch bus).
    """
    out = []
    for i, e in enumerate(g.edges):
        for j in range(i + 1, len(g.edges)):
            f = g.edges[j]
            joinable = e.dst == f.dst or e.points[0] == f.points[0]
            for s in _segs(e.points):
                for t in _segs(f.points):
                    off, ov = _parallel(s, t)
                    if off < 0 or ov <= 2.0:
                        continue
                    if off < EPS and joinable:
                        continue
                    out.append(f"{g.name}: E{i} {s} vs E{j} {t}: "
                               f"offset {off:.1f}, overlap {ov:.0f}")
    return out


def problems(graphs: list[LGraph]) -> list[str]:
    res = []
    for g in graphs:
        res += node_hits(g) + edge_overlaps(g)
    return res
