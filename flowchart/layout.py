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

MERGE_SIZE = 10.0


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


def _route(a: tuple[float, float], b: tuple[float, float],
           sp: str, dp: str, src: LNode, dst: LNode,
           down: bool = True,
           obstacles: list[LNode] | None = None,
           lane: int = 0) -> list[tuple[float, float]]:
    """Orthogonal route between two ports.

    `lane` separates parallel corridors that would otherwise share one
    x coordinate: 0 = branch exits ("no" arms), 1 = loop back edges.
    """
    (xs, ys), (xd, yd) = a, b
    src_left, src_right = src.x, src.x + src.w
    dst_left, dst_right = dst.x, dst.x + dst.w
    if abs(xs - xd) < 1 and abs(ys - yd) < 1:
        return [a, b]
    if sp == "b" and dp == "t":
        if abs(xs - xd) < 1 and down:
            return [a, b]
        if not down:
            # back edge: down a little, loop right around the whole body,
            # rejoin the approach line above the target (never enter the
            # target block itself). The corridor dodges every visible
            # block stacked between the two rows.
            join_y = yd - 16
            base = max(src_right, dst_right) + 22 + lane * 26
            xc = base
            if obstacles:
                top, bot = min(ys, join_y), max(ys, join_y)
                need = base
                for ob in obstacles:
                    if ob.id in (src.id, dst.id) or ob.kind == "merge":
                        continue
                    if ob.y < bot and ob.y + ob.h > top:
                        need = max(need, ob.x + ob.w + 14)
                # the dodge must preserve the lane separation: if the
                # obstacle pushes this lane onto another lane's corridor,
                # step one full lane further out
                if need > base:
                    xc = need + lane * 26
                else:
                    xc = base
            return [a, (xs, ys + 14), (xc, ys + 14), (xc, join_y),
                    (xd, join_y)]
        ym = (ys + yd) / 2
        if ym > ys + 10:
            return [a, (xs, ym), (xd, ym), b]
        xc = src_right + 18
        return [a, (xc, ys), (xc, yd - 18), (xd, yd - 18), b]
    if sp == "r" and dp == "t":
        if yd > ys + 8 and xd > xs + 5:
            # target centre is right of the exit point: step right, then down
            return [a, (xd, ys), b]
        # target in the same/left column: loop right around the source
        # block and everything the branch has to clear, then down.
        # The corridor is pushed past every visible block stacked between
        # the source and target rows so the vertical drop cannot run
        # through a foreign block. Lane 0 (branch exits) stays closest;
        # back edges use lane 1 and are routed further out.
        base = max(src_right, dst_right) + 22 + lane * 26
        xc = base
        if obstacles:
            top, bot = min(ys, yd), max(ys, yd)
            need = base
            for ob in obstacles:
                if ob.id in (src.id, dst.id) or ob.kind == "merge":
                    continue
                if ob.y < bot and ob.y + ob.h > top:
                    need = max(need, ob.x + ob.w + 14)
            xc = need if need <= base else need + lane * 26
        join_y = yd - 18
        return [a, (xc, ys), (xc, join_y), (xd, join_y), b]
    if sp == "b" and dp == "l":
        # counter-loop back edge: down, around everything on the LEFT
        # (wide body blocks may stick out to the right of the hexagon),
        # up, and rightwards into the left edge of the hexagon. The graph
        # marks these edges 'always' so the arrowhead is kept.
        # The corridor hugs the left side of the hexagon column; obstacles
        # to the left push it further left, the canvas margin is the limit.
        join_y = yd
        base = min(src_left, dst_left) - 24 - lane * 26
        xc = base
        if obstacles:
            top, bot = min(ys, join_y), max(ys, join_y)
            need = base
            for ob in obstacles:
                if ob.id in (src.id, dst.id) or ob.kind == "merge":
                    continue
                if ob.y < bot and ob.y + ob.h > top:
                    need = min(need, ob.x - 14)
            xc = need if need >= base else need - lane * 26
        return [a, (xs, ys + 16), (xc, ys + 16), (xc, join_y), b]
    if sp in ("l", "r") and dp in ("l", "r"):
        if sp == "l":
            xc = min(xs, xd, src_left) - 20
        else:
            xc = max(xs, xd, src_right) + 20
        return [a, (xc, ys), (xc, yd), b]
    if sp == "b" and dp == "r":
        return [a, (xs, yd), b]
    xc = xs + (26 if sp in ("r", "b") else -26)
    return [a, (xc, ys), (xc, yd), b]


def _crosses(x0: float, x1: float, y0: float, y1: float, node: LNode) -> bool:
    """True if the vertical corridor between y0..y1 at x0..x1 hits `node`."""
    return (node.y < y1 and node.y + node.h > y0
            and node.x < x1 and node.x + node.w > x0)


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
                group = ({e.src} | set(below(e.src))) - set(fwd(e.dst)) \
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

    # ---- 3. x from columns ----------------------------------------------
    nodes: dict[int, LNode] = {}
    for n in active_nodes:
        w, h, lines = sizes[n.id]
        cx = COL_MARGIN / 2 + n.col * colw + colw / 2
        nodes[n.id] = LNode(n.id, n.kind, cx - w / 2, y[n.id], w, h, lines)

    # ---- 4. edges --------------------------------------------------------
    edges: list[LEdge] = []
    all_nodes = list(nodes.values())
    for e in vis_edges:
        if e.src not in nodes or e.dst not in nodes:
            continue
        a = _port(nodes[e.src], e.src_port)
        b = _port(nodes[e.dst], e.dst_port)
        lane = 0 if e.down else 1
        pts = _route(a, b, e.src_port, e.dst_port,
                     nodes[e.src], nodes[e.dst], down=e.down,
                     obstacles=all_nodes, lane=lane)
        le = LEdge(points=pts, label=e.label, arrow=e.arrow)
        if e.label:
            le.lx, le.ly, le.anchor = _label_pos(pts)
        edges.append(le)

    width = (max(n.col for n in active_nodes) + 1) * colw + COL_MARGIN
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

