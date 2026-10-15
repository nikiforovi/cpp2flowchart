"""Geometry layout for flowchart graphs: node sizes, columns, edge routing."""

from __future__ import annotations

from dataclasses import dataclass

from .graph import Graph

VGAP = 44          # vertical gap between stacked nodes
COL_MARGIN = 56    # horizontal padding between columns
NODE_MIN_W = 120
FONT_CHAR_W = 7.1  # approx char width at 12px
LINE_H = 16

_WRAP = {
    "terminal": 34,
    "process": 30,
    "io": 28,
    "decision": 22,
    "hexagon": 26,
    "connector": 12,
    "merge": 12,
}

_PAD = {"terminal": (34, 18), "process": (28, 22),
        "io": (30, 22), "decision": (44, 34), "hexagon": (56, 24),
        "connector": (24, 10), "merge": (10, 10)}

# merge anchors are invisible junction points: zero size, so the joining
# lines and the outgoing line meet in one point (no gap in the line)
MERGE_SIZE = 0.0


@dataclass
class LNode:
    id: int
    kind: str
    x: float
    y: float
    w: float
    h: float
    lines: list[str]


@dataclass
class LEdge:
    points: list[tuple[float, float]]
    label: str = ""
    lx: float = 0.0
    ly: float = 0.0
    anchor: str = "middle"
    arrow: str = "auto"   # 'auto' (GOST direction rule) | 'always' | 'never'
    src: int = -1         # id of the source LNode
    dst: int = -1         # id of the target LNode


def _needs_arrow(pts: list[tuple[float, float]]) -> bool:
    """GOST 19.701-90: arrows only where flow is not top-down/left-right.

    The default direction needs no arrow; an arrow is required when the
    final segment runs upward or right-to-left.
    """
    if len(pts) < 2:
        return False
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    if abs(dy) >= abs(dx):
        return dy < -0.5  # upward
    return dx < -0.5  # right-to-left


def edge_arrow(pts: list[tuple[float, float]], mode: str) -> bool:
    """Whether to draw an arrow head for an edge with the given mode."""
    if mode == "never":
        return False
    if mode == "always":
        return True
    return _needs_arrow(pts)


def _label_pos(pts: list[tuple[float, float]]) -> tuple[float, float, str]:
    """Place a branch label near the first segment long enough to hold it."""
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        if abs(dy) >= abs(dx):
            if abs(dy) < 12:
                continue  # too short
            return (x0 + 8, (y0 + y1) / 2, "start" if dx >= -0.1 else "end")
        if abs(dx) < 14:
            continue
        return ((x0 + x1) / 2, y0 - 6, "middle")
    x0, y0 = pts[0]
    return (x0 + 8, y0 - 6, "start")


@dataclass
class LGraph:
    name: str
    signature: str
    nodes: list[LNode]
    edges: list[LEdge]
    width: float
    height: float
    start: int = 0
    end: int = 0


def _wrap(text: str, limit: int) -> list[str]:
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= limit or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    out: list[str] = []
    for ln in lines:
        while len(ln) > limit + 8:
            out.append(ln[:limit + 8])
            ln = ln[limit + 8:]
        out.append(ln)
    return out or [""]


def _port(node: LNode, port: str) -> tuple[float, float]:
    if port == "t":
        return (node.x + node.w / 2, node.y)
    if port == "b":
        return (node.x + node.w / 2, node.y + node.h)
    if port == "l":
        return (node.x, node.y + node.h / 2)
    return (node.x + node.w, node.y + node.h / 2)


LANE_GAP = 26.0          # distance between parallel side corridors
CORRIDOR_PAD = 14.0      # clearance between a corridor and a block
MIN_CORRIDOR_GAP = 22.0  # two live corridors never run closer than this


def _iv_overlap(s0: tuple[float, float], s1: tuple[float, float]) -> float:
    """Length of the overlap of two 1D intervals (0 when they only touch)."""
    lo = max(min(s0[0], s0[1]), min(s1[0], s1[1]))
    hi = min(max(s0[0], s0[1]), max(s1[0], s1[1]))
    return max(0.0, hi - lo)


def _straight_blocked(a, b, src: LNode, dst: LNode,
                      obstacles: list[LNode] | None) -> bool:
    """Does the straight drop from `a` to `b` run through a foreign block?

    Invisible merge anchors count too: a line running straight through
    somebody else's junction point would look like it joins there (e.g.
    a `break` dropping through the loop-back junction below it).
    """
    (xs, ys), (_, yd) = a, b
    for ob in obstacles or ():
        if ob.id in (src.id, dst.id):
            continue
        if _crosses(xs - 2, xs + 2, min(ys, yd), max(ys, yd), ob):
            return True
    return False


def _push_right(a, b, src: LNode, dst: LNode,
                obstacles: list[LNode] | None) -> float:
    """x of the right-hand corridor that clears every block in between."""
    (xs, ys), (xd, yd) = a, b
    top, bot = min(ys, yd), max(ys, yd)
    need = max(src.x + src.w, dst.x + dst.w) + 22
    for ob in obstacles or ():
        if ob.id in (src.id, dst.id) or ob.kind == "merge":
            continue
        if ob.y < bot and ob.y + ob.h > top:
            need = max(need, ob.x + ob.w + CORRIDOR_PAD)
    return need


def _push_left(a, b, src: LNode, dst: LNode,
               obstacles: list[LNode] | None,
               span: tuple[float, float] | None = None) -> float:
    """x of the left-hand corridor that clears every block in between."""
    (xs, ys), (xd, yd) = a, b
    top, bot = span if span else (min(ys, yd), max(ys, yd))
    need = min(src.x, dst.x) - 22
    for ob in obstacles or ():
        if ob.id in (src.id, dst.id) or ob.kind == "merge":
            continue
        if ob.y < bot and ob.y + ob.h > top:
            need = min(need, ob.x - CORRIDOR_PAD)
    return need


def _route(a: tuple[float, float], b: tuple[float, float],
           sp: str, dp: str, src: LNode, dst: LNode,
           down: bool = True,
           obstacles: list[LNode] | None = None,
           lane: int = 0,
           xc: float | None = None) -> list[tuple[float, float]]:
    """Orthogonal route between two ports.

    `xc` overrides the side-corridor x (set after corridor de-collision);
    `lane` is only consulted when no explicit corridor is given.
    """
    (xs, ys), (xd, yd) = a, b
    src_left, src_right = src.x, src.x + src.w
    dst_left, dst_right = dst.x, dst.x + dst.w
    if abs(xs - xd) < 1 and abs(ys - yd) < 1:
        return [a, b]
    if sp == "b" and dp == "t":
        if not down:
            # back edge: down a little, loop around the whole body on the
            # LEFT (the "нет" exit of the same loop leaves to the right, so
            # the two never cross), rejoin the approach line above the
            # target (never enter the target block itself).
            if xc is None:
                span = (min(yd - 16, ys + 14), max(yd - 16, ys + 14))
                xc = _push_left(a, b, src, dst, obstacles, span) \
                    - lane * LANE_GAP
            join_y = yd - 16
            return [a, (xs, ys + 14), (xc, ys + 14), (xc, join_y),
                    (xd, join_y), b]
        if abs(xs - xd) < 1 and not _straight_blocked(a, b, src, dst,
                                                      obstacles):
            return [a, b]
        if xc is None:
            xc = _push_right(a, b, src, dst, obstacles) + lane * LANE_GAP
        if abs(xs - xd) < 1:
            # long exit (e.g. an early `return`): detour around every block
            # stacked in between and rejoin above the target
            join_y = yd - 18
            return [a, (xs, ys + 14), (xc, ys + 14), (xc, join_y),
                    (xd, join_y), b]
        # turn as close to the target as possible: the final vertical
        # stretch at xd is where this edge would run on top of whatever
        # other line already occupies that column (e.g. the "да" branch
        # dropping straight into the same merge), so keep it short rather
        # than using the midpoint (which made the shared stretch huge)
        turn_y = yd - 18
        if turn_y > ys + 10:
            return [a, (xs, turn_y), (xd, turn_y), b]
        return [a, (xc, ys), (xc, yd - 18), (xd, yd - 18), b]
    if sp == "r" and dp == "t":
        if yd > ys + 8 and xd > xs + 5:
            # target centre is right of the exit point: step right, then down
            return [a, (xd, ys), b]
        # target in the same/left column: loop right around the source
        # block and everything the branch has to clear, then down
        if xc is None:
            xc = _push_right(a, b, src, dst, obstacles) + lane * LANE_GAP
        join_y = yd - 18
        return [a, (xc, ys), (xc, join_y), (xd, join_y), b]
    if sp == "b" and dp == "l":
        # counter-loop back edge: down, around everything on the LEFT (wide
        # body blocks may stick out to the right of the hexagon), up, and
        # rightwards into the left edge of the hexagon.
        span = (min(yd, ys + 16), max(yd, ys + 16))
        if xc is None:
            xc = _push_left(a, b, src, dst, obstacles, span) - lane * LANE_GAP
        return [a, (xs, ys + 16), (xc, ys + 16), (xc, yd), b]
    if sp == "r" and dp == "l":
        # an enclosing counter loop fed from the exit of a nested loop:
        # step right, drop clear of the source block, sweep left around
        # everything, climb, and enter the counter's left edge
        drop = src.y + src.h + 16
        span = (min(drop, yd), max(drop, yd))
        if xc is None:
            xc = _push_left(a, b, src, dst, obstacles, span) - lane * LANE_GAP
        return [a, (src_right + 18, ys), (src_right + 18, drop),
                (xc, drop), (xc, yd), b]
    if sp in ("l", "r") and dp in ("l", "r"):
        if xc is None:
            xc = (min(xs, xd, src_left) - 20 if sp == "l"
                  else max(xs, xd, src_right) + 20)
        return [a, (xc, ys), (xc, yd), b]
    if sp == "b" and dp == "r":
        return [a, (xs, yd), b]
    xc = xs + (26 if sp in ("r", "b") else -26)
    return [a, (xc, ys), (xc, yd), b]


def _corridor_sides(e, a, b, src: LNode, dst: LNode,
                    obstacles: list[LNode]) -> tuple[str, ...]:
    """Sides on which `e` may run a side corridor; () for a fixed route.

    Must agree with the branches of `_route` that consult `xc`.
    """
    (xs, ys), (xd, yd) = a, b
    sp, dp = e.src_port, e.dst_port
    if sp == "b" and dp == "t":
        if not e.down:
            return ("l",)
        if abs(xs - xd) < 1:
            if abs(ys - yd) >= 1 and _straight_blocked(a, b, src, dst,
                                                       obstacles):
                return ("r", "l")  # detour on whichever side is clear
            return ()
        if yd - 18 > ys + 10:
            return ()  # plain Z-route
        return ("r",)
    if sp == "r" and dp == "t":
        if yd > ys + 8 and xd > xs + 5:
            return ()  # plain L-route
        return ("r",)
    if sp == "b" and dp == "l":
        return ("l",)
    if sp == "r" and dp == "l":
        return ("l",)
    if sp in ("l", "r") and dp in ("l", "r"):
        return ("l",) if sp == "l" else ("r",)
    return ()


# ---- route validation --------------------------------------------------
# A candidate route is scored by (violations, crossings): a violation is a
# line through a block / foreign junction point, or a line running on top
# of (or hugging) another line it does not legitimately join; a crossing
# is a plain perpendicular intersection - allowed, but kept to a minimum.

H_SEP = 8.0   # parallel horizontal lines closer than this look merged


def _seg_hits_box(p, q, n: LNode, pad: float) -> bool:
    """Does segment p-q enter the box of `n` grown by `pad` (may be < 0)?"""
    lx, hx = min(p[0], q[0]), max(p[0], q[0])
    ly, hy = min(p[1], q[1]), max(p[1], q[1])
    return (lx < n.x + n.w + pad and hx > n.x - pad
            and ly < n.y + n.h + pad and hy > n.y - pad)


def _seg_through_point(p, q, pt) -> bool:
    """Does `pt` lie strictly inside the axis-aligned segment p-q?"""
    (x0, y0), (x1, y1) = p, q
    px, py = pt
    if abs(x0 - x1) < 0.5:  # vertical
        return (abs(px - x0) < 0.5
                and min(y0, y1) + 0.5 < py < max(y0, y1) - 0.5)
    return (abs(py - y0) < 0.5
            and min(x0, x1) + 0.5 < px < max(x0, x1) - 0.5)


def _seg_pair(p, q, r, s, joinable: bool) -> tuple[int, int]:
    """(violations, crossings) between two axis-aligned segments."""
    pv = abs(p[0] - q[0]) < 0.5
    rv = abs(r[0] - s[0]) < 0.5
    if pv == rv:
        if pv:
            off = abs(p[0] - r[0])
            ov = _iv_overlap((p[1], q[1]), (r[1], s[1]))
            sep = MIN_CORRIDOR_GAP
        else:
            off = abs(p[1] - r[1])
            ov = _iv_overlap((p[0], q[0]), (r[0], s[0]))
            sep = H_SEP
        if ov <= 1.0:
            return 0, 0
        if off < 0.5:
            return (0 if joinable else 1), 0
        return (1 if off < sep else 0), 0
    v0, v1, h0, h1 = (p, q, r, s) if pv else (r, s, p, q)
    vx = v0[0]
    hy = h0[1]
    in_h = min(h0[0], h1[0]) - 0.5 <= vx <= max(h0[0], h1[0]) + 0.5
    in_v = min(v0[1], v1[1]) - 0.5 <= hy <= max(v0[1], v1[1]) + 0.5
    if not (in_h and in_v):
        return 0, 0
    strict_h = min(h0[0], h1[0]) + 0.5 < vx < max(h0[0], h1[0]) - 0.5
    strict_v = min(v0[1], v1[1]) + 0.5 < hy < max(v0[1], v1[1]) - 0.5
    if strict_h and strict_v:
        return 0, 1
    if strict_h or strict_v:
        # a line ending on another one reads as a junction
        return (0 if joinable else 1), 0
    return 0, 0  # corner touches corner


def _route_cost(pts, src: LNode, dst: LNode, nodes: list[LNode],
                placed: list[tuple[int, list[tuple[float, float]]]]
                ) -> tuple[int, int]:
    bad = cross = 0
    segs = list(zip(pts, pts[1:]))
    for p, q in segs:
        for n in nodes:
            if n.kind == "merge":
                if n.id not in (src.id, dst.id) and \
                        _seg_through_point(p, q, (n.x, n.y)):
                    bad += 1
                continue
            if n.id in (src.id, dst.id):
                if _seg_hits_box(p, q, n, -1.0):
                    bad += 1
            elif _seg_hits_box(p, q, n, 2.0):
                bad += 1
    for fdst, fpts in placed:
        joinable = fdst == dst.id or fpts[0] == pts[0]
        for r, s in zip(fpts, fpts[1:]):
            for p, q in segs:
                v, c = _seg_pair(p, q, r, s, joinable)
                bad += v
                cross += c
    return bad, cross


def _candidates(side: str, base: float, nodes: list[LNode],
                placed: list[tuple[int, list[tuple[float, float]]]]
                ) -> list[float]:
    """Corridor x positions worth trying, nearest to `base` first."""
    xs = {base}
    for n in nodes:
        if n.kind == "merge":
            continue
        xs.add(n.x - CORRIDOR_PAD)
        xs.add(n.x + n.w + CORRIDOR_PAD)
    for _, fpts in placed:
        for (x0, y0), (x1, y1) in zip(fpts, fpts[1:]):
            if abs(x0 - x1) < 0.5:
                xs.add(x0 - MIN_CORRIDOR_GAP)
                xs.add(x0 + MIN_CORRIDOR_GAP)
    if side == "r":
        far = max([base] + [x for x in xs]) + LANE_GAP
        out = sorted(x for x in xs | {far} if x >= base - 1e-6)
    else:
        far = min([base] + [x for x in xs]) - LANE_GAP
        out = sorted((x for x in xs | {far} if x <= base + 1e-6),
                     reverse=True)
    return out


def _crosses(x0: float, x1: float, y0: float, y1: float, node: LNode) -> bool:
    """True if the vertical corridor between y0..y1 at x0..x1 hits `node`."""
    return (node.y < y1 and node.y + node.h > y0
            and node.x < x1 and node.x + node.w > x0)


def _place_and_route(active_nodes, sizes, y, colw: float, extra: list[float],
                     vis_edges):
    """Place nodes on their columns and route every edge.

    Fixed routes (straight drops, L/Z shapes) go first. Side corridors
    follow, innermost (shortest) first: each one tries candidate x
    positions outward from the blocks it serves and takes the one whose
    *whole* route is cheapest - no blocks or foreign junctions hit, no
    line running on top of another, fewest crossings, closest in.

    Returns (nodes, edges, failed) where `failed` lists (side, column)
    of corridors that found no clean position.
    """
    shift, acc = [], 0.0
    for ex in extra:
        acc += ex
        shift.append(acc)
    nodes: dict[int, LNode] = {}
    cols: dict[int, int] = {}
    for n in active_nodes:
        w, h, lines = sizes[n.id]
        cx = COL_MARGIN / 2 + n.col * colw + colw / 2 + shift[n.col]
        nodes[n.id] = LNode(n.id, n.kind, cx - w / 2, y[n.id], w, h, lines)
        cols[n.id] = n.col
    all_nodes = list(nodes.values())

    routed: dict[int, list[tuple[float, float]]] = {}
    placed: list[tuple[int, list[tuple[float, float]]]] = []
    jobs = []
    for idx, e in enumerate(vis_edges):
        if e.src not in nodes or e.dst not in nodes:
            continue
        src, dst = nodes[e.src], nodes[e.dst]
        a, b = _port(src, e.src_port), _port(dst, e.dst_port)
        sides = _corridor_sides(e, a, b, src, dst, all_nodes)
        if sides:
            jobs.append((abs(b[1] - a[1]), idx, e, a, b, sides))
            continue
        pts = _route(a, b, e.src_port, e.dst_port, src, dst, down=e.down,
                     obstacles=all_nodes)
        routed[idx] = pts
        placed.append((e.dst, pts))

    failed: list[tuple[str, int]] = []
    for _, idx, e, a, b, sides in sorted(jobs, key=lambda j: (j[0], j[1])):
        src, dst = nodes[e.src], nodes[e.dst]
        best = None
        for side in sides:
            if side == "r":
                base = max(src.x + src.w, dst.x + dst.w) + 22
            else:
                base = min(src.x, dst.x) - 22
            for xc in _candidates(side, base, all_nodes, placed):
                pts = _route(a, b, e.src_port, e.dst_port, src, dst,
                             down=e.down, obstacles=all_nodes, xc=xc)
                bad, cross = _route_cost(pts, src, dst, all_nodes, placed)
                key = (bad, cross, abs(xc - base))
                if best is None or key < best[0]:
                    best = (key, pts, side)
                if bad == 0 and cross == 0:
                    break  # nearest clean position on this side
        (bad, _, _), pts, side = best
        if bad:
            col = (min(cols[e.src], cols[e.dst]) if side == "l"
                   else max(cols[e.src], cols[e.dst]))
            failed.append((side, col))
        routed[idx] = pts
        placed.append((e.dst, pts))

    edges: list[LEdge] = []
    for idx, e in enumerate(vis_edges):
        if idx not in routed:
            continue
        pts = routed[idx]
        le = LEdge(points=pts, label=e.label, arrow=e.arrow,
                   src=e.src, dst=e.dst)
        if e.label:
            le.lx, le.ly, le.anchor = _label_pos(pts)
        edges.append(le)
    return nodes, edges, failed


def layout(graph: Graph) -> LGraph:
    skip = {n.id for n in graph.nodes if n.kind == "skip"}
    active_nodes = [n for n in graph.nodes if n.id not in skip]
    active_ids = {n.id for n in active_nodes}
    vis_end = graph.end if graph.end not in skip else -1
    # edges into a hidden end marker are pure exits: they must not order
    # unrelated branches below each other (that ratchets heights)
    vis_edges = [
        e for e in graph.edges
        if not (e.dst == graph.end and vis_end < 0)
    ]
    # ---- 1. node sizes -------------------------------------------------
    sizes: dict[int, tuple[float, float, list[str]]] = {}
    max_w = 0.0
    for n in active_nodes:
        limit = _WRAP.get(n.kind, 28)
        lines = _wrap(n.text, limit) if n.kind != "merge" else [""]
        pad_x, pad_y = _PAD.get(n.kind, (28, 22))
        w = max(NODE_MIN_W, max(len(l) for l in lines) * FONT_CHAR_W + pad_x)
        h = len(lines) * LINE_H + pad_y
        if n.kind == "connector":
            w = max(78.0, len(n.text) * FONT_CHAR_W + pad_x)
            h = 30.0
        if n.kind == "merge":
            w = MERGE_SIZE
            h = MERGE_SIZE
        if n.kind == "terminal":
            h = max(38.0, h)
        if n.kind == "decision":
            h = max(58.0, h)
        if n.kind == "hexagon":
            h = max(48.0, h)
        sizes[n.id] = (w, h, lines)
        max_w = max(max_w, w)

    colw = max_w + COL_MARGIN

    # ---- 2. y positions via longest-path relaxation ---------------------
    # Right-side ("no") branches must start below the whole "yes" subtree,
    # not just below the decision node itself.
    out_edges: dict[int, list[tuple[str, int]]] = {}
    for e in vis_edges:
        if e.down and e.dst_port == "t":
            if e.src in skip or e.dst in skip:
                continue
            out_edges.setdefault(e.src, []).append((e.src_port, e.dst))

    from functools import lru_cache

    @lru_cache(maxsize=None)
    def fwd(nid: int) -> frozenset[int]:
        """Nodes on the continuation after nid (through normal tails)."""
        out: set[int] = set()
        stack = [nid]
        while stack:
            u = stack.pop()
            for sp, dst in out_edges.get(u, ()):
                if dst == graph.end or dst in out or dst == nid:
                    continue
                out.add(dst)
                stack.append(dst)
        return frozenset(out)

    @lru_cache(maxsize=None)
    def below(nid: int) -> frozenset[int]:
        """Nodes of the "yes" subtree that a right-side branch must clear.

        Follows only bottom-port exits starting from nid's own bottom
        successors - i.e. the straight "yes" flow plus anything nested
        inside it. Right-side exits of nid are the branch being
        positioned; right-side exits deeper inside (nested branches)
        still count since they rejoin the local flow. Connector nodes
        (break/continue) terminate the walk: their outgoing edges leave
        the current construct. Stops at the graph end.
        """
        out: set[int] = set()
        stack = [dst for sp, dst in out_edges.get(nid, ()) if sp == "b"]
        while stack:
            u = stack.pop()
            if u == graph.end or u in out or u == nid:
                continue
            out.add(u)
            if graph.nodes[u].kind == "connector":
                continue  # break/continue leave this construct
            for sp, dst in out_edges.get(u, ()):
                if u == nid and sp == "r":
                    continue  # that is the branch itself
                if dst == graph.end or dst in out or dst == nid:
                    continue
                stack.append(dst)
        return frozenset(out)

    y: dict[int, float] = {graph.start: 0.0}
    for _ in range(len(graph.nodes) + 2):
        changed = False
        for e in vis_edges:
            if not e.down or e.src not in y or e.dst == graph.end:
                continue
            if e.src_port == "r":
                # Exclude the branch target's own continuation: the target
                # is usually reachable from src through the "yes" subtree,
                # and pulling its successors into the base ratchets the
                # target's own y upward on every relaxation pass.
                sub = set(below(e.src))
                if e.compact:
                    # the "да" side ends at its own terminal: only blocks
                    # of it that reach into the branch's columns matter
                    dcol = graph.nodes[e.dst].col
                    sub = {g for g in sub if graph.nodes[g].col >= dcol}
                group = ({e.src} | sub) - set(fwd(e.dst)) \
                    - {e.dst} or {e.src}
                if not all(g in y for g in group):
                    continue
                base = max(y[g] + sizes[g][1] for g in group)
                cand = base + VGAP
            else:
                cand = y[e.src] + sizes[e.src][1] + VGAP
            if e.dst not in y or y[e.dst] < cand - 1e-6:
                y[e.dst] = cand
                changed = True
        if not changed:
            break
    # unconnected nodes (dead code) stack after everything placed so far
    cur_max = max((y[i] + sizes[i][1]) for i in y) if y else 0.0
    for n in active_nodes:
        if n.id not in y:
            cur_max += VGAP
            y[n.id] = cur_max - sizes[n.id][1]
    # the end marker always goes to the very bottom (when visible)
    end_y = max(y[i] + sizes[i][1] for i in y) + VGAP
    if graph.end in sizes:
        y[graph.end] = end_y
    else:
        end_y -= VGAP

    # ---- 3+4. x from columns, edge routing -------------------------------
    # Column gaps start uniform. When a side corridor cannot be routed
    # cleanly (no room left between neighbouring columns), the gap in
    # front of the offending column is widened and everything re-routed.
    max_col = max(n.col for n in active_nodes)
    extra = [0.0] * (max_col + 1)
    best = None
    for _ in range(12):
        nodes, edges, failed = _place_and_route(
            active_nodes, sizes, y, colw, extra, vis_edges)
        if best is None or len(failed) < best[0]:
            best = (len(failed), nodes, edges)
        if not failed:
            break
        grow = {col if side == "l" else col + 1 for side, col in failed}
        grow = {c for c in grow if 1 <= c <= max_col}
        if not grow:
            break  # not a matter of room: keep the least bad routing
        for c in grow:
            extra[c] += LANE_GAP
    _, nodes, edges = best

    width = (max_col + 1) * colw + COL_MARGIN + sum(extra)
    width = max(width, max(
        [nd.x + nd.w for nd in nodes.values()]
        + [px for e in edges for px, _ in e.points]
    ) + COL_MARGIN / 2)
    height = max(nd.y + nd.h for nd in nodes.values()) + VGAP
    # left-side loop corridors may stick out past x=0: shift everything
    # right so nothing is clipped
    min_x = min(
        [nd.x for nd in nodes.values()]
        + [px for e in edges for px, _ in e.points]
    )
    if min_x < 8:
        shift = 8 - min_x
        for nd in nodes.values():
            nd.x += shift
        for e in edges:
            e.points = [(px + shift, py) for px, py in e.points]
            e.lx += shift
        width += shift
    end_id = vis_end if vis_end in nodes else graph.start
    # when the end marker is hidden, the start terminal still anchors
    # the layout: keep `end` pointing at a real lowest node instead
    if end_id == graph.start and active_nodes:
        lowest = max(nodes.values(), key=lambda nd: nd.y + nd.h)
        end_id = lowest.id
    return LGraph(
        name=graph.name,
        signature=graph.signature,
        nodes=list(nodes.values()),
        edges=edges,
        width=width,
        height=height,
        start=graph.start,
        end=end_id,
    )


def layout_all(graphs: list[Graph]) -> list[LGraph]:
    return [layout(g) for g in graphs]

