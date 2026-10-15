"""GOST 19.701-90 conformance tests: structure, geometry, texts."""

from pathlib import Path

import pytest

from flowchart.convert import convert
from flowchart.graph import build_graphs, for_counter_text
from flowchart.layout import LGraph
from flowchart.parser import ParseError, parse_cpp


def graph_of(src, name=None):
    gs = build_graphs(parse_cpp(src))
    return next(g for g in gs if name is None or g.name == name)


def layout_of(src) -> LGraph:
    return convert(src)[0]


# ---------------------------------------------------------------- 1. if/else
class TestIf:
    def test_if_without_else_has_merge(self):
        g = graph_of("void f() { if (c) a(); b(); }")
        merges = [n for n in g.nodes if n.kind == "merge"]
        assert len(merges) == 1
        dec = next(n for n in g.nodes if n.kind == "decision")
        body = next(n for n in g.nodes if n.text == "a()")
        # "да" enters the body, "нет" goes straight to the merge,
        # body flows on into the merge
        assert any(
            e.src == dec.id and e.dst == body.id and e.label == "да"
            for e in g.edges
        )
        assert any(
            e.src == dec.id and e.dst == merges[0].id and e.label == "нет"
            for e in g.edges
        )
        assert any(
            e.src == body.id and e.dst == merges[0].id for e in g.edges
        )

    def test_if_else_joins_then_continues(self):
        g = graph_of("void f() { if (c) a(); else b(); d(); }")
        merge = next(n for n in g.nodes if n.kind == "merge")
        after = next(n for n in g.nodes if n.text == "d()")
        assert any(e.src == merge.id and e.dst == after.id for e in g.edges)

    def test_nested_if_else(self):
        src = """
        void f() {
            if (a) {
                if (b) x(); else y();
            } else {
                z();
            }
            w();
        }
        """
        g = graph_of(src)
        merges = [n for n in g.nodes if n.kind == "merge"]
        assert len(merges) == 2
        w = next(n for n in g.nodes if n.text == "w()")
        assert any(
            any(e.src == n.id and e.dst == w.id for e in g.edges)
            for n in merges
        )

    def test_empty_then_branch(self):
        g = graph_of("void f() { if (c) { } a(); }")
        dec = next(n for n in g.nodes if n.kind == "decision")
        merge = next(n for n in g.nodes if n.kind == "merge")
        assert any(
            e.src == dec.id and e.dst == merge.id and e.label == "да"
            for e in g.edges
        )


# ------------------------------------------------------------------ 2. for
class TestForCounter:
    def test_for_step_2(self):
        g = graph_of(
            "void f() { for (int i = 0; i <= 10; i += 2) { a(); } }"
        )
        hexes = [n for n in g.nodes if n.kind == "hexagon"]
        assert len(hexes) == 1
        assert hexes[0].text == "i = 0,10,2"

    def test_for_inclusive_limit_reached(self):
        g = graph_of(
            "void f() { for (int i = 0; i <= 10; i += 3) { a(); } }"
        )
        hexes = next(n for n in g.nodes if n.kind == "hexagon")
        # 10 is not on the 0,3,6,9 grid -> limit trimmed to 9
        assert hexes.text == "i = 0,9,3"

    def test_for_negative_step(self):
        g = graph_of(
            "void f() { for (int i = 10; i >= 0; i -= 2) { a(); } }"
        )
        hexes = next(n for n in g.nodes if n.kind == "hexagon")
        assert hexes.text == "i = 10,0,-2"

    def test_for_decrement_operator(self):
        g = graph_of(
            "void f() { for (int i = 5; i > 0; i--) { a(); } }"
        )
        hexes = next(n for n in g.nodes if n.kind == "hexagon")
        assert hexes.text == "i = 5,1,-1"

    def test_for_fallback_documents_all_parts(self):
        g = graph_of(
            "void f() { for (p = head; p != 0; p = p->next) { a(); } }"
        )
        hexes = next(n for n in g.nodes if n.kind == "hexagon")
        assert "p = head" in hexes.text and "p != 0" in hexes.text

    def test_for_no_types_in_text(self):
        g = graph_of(
            "void f() { for (int i = 0; i < 10; i++) { int x = 1; a(); } }"
        )
        texts = [n.text for n in g.nodes]
        assert not any(t.startswith("int ") for t in texts)
        assert "x = 1" in texts

    def test_for_counter_text_unit(self):
        from flowchart import nodes as N
        s = N.For(init="int i = 0", cond="i <= 10", step="i += 2")
        assert for_counter_text(s) == "i = 0,10,2"


# ------------------------------------------------------------------ 3. loops
class TestLoops:
    def test_while_back_edge_joins_entry_line(self):
        g = graph_of("void f() { while (c) { a(); b(); } d(); }")
        dec = next(n for n in g.nodes if n.kind == "decision")
        back = [
            e for e in g.edges
            if e.dst == dec.id and e.dst_port == "t" and not e.down
        ]
        assert len(back) == 1
        assert back[0].arrow == "always"

    def test_do_while_back_to_body_entry(self):
        g = graph_of("void f() { do { a(); b(); } while (c); d(); }")
        dec = next(n for n in g.nodes if n.kind == "decision")
        first = next(n for n in g.nodes if n.text == "a()")
        back = [e for e in g.edges if e.src == dec.id and e.dst == first.id]
        assert len(back) == 1
        assert back[0].dst_port == "t" and not back[0].down
        assert back[0].label == "да"

    def test_while_break_continue(self):
        g = graph_of(
            "void f() { while (c) { if (d) break; if (e) continue; a(); } b(); }"
        )
        brk = next(n for n in g.nodes if n.text == "break")
        cont = next(n for n in g.nodes if n.text == "continue")
        dec = next(n for n in g.nodes if n.kind == "decision")
        b_node = next(n for n in g.nodes if n.text == "b()")
        assert any(e.dst == b_node.id for e in g.edges if e.src == brk.id)
        # continue may first join a shared junction with the other
        # loop-back tail instead of a direct edge into the condition
        seen = {cont.id}
        frontier = {cont.id}
        while frontier:
            frontier = {e.dst for e in g.edges if e.src in frontier} - seen
            seen |= frontier
        assert dec.id in seen

    def test_nested_loops_break_targets_inner(self):
        src = """
        void f() {
            while (a) {
                while (b) {
                    if (c) break;
                }
                d();
            }
            e();
        }
        """
        g = graph_of(src)
        brk = next(n for n in g.nodes if n.text == "break")
        d_node = next(n for n in g.nodes if n.text == "d()")
        assert any(e.dst == d_node.id for e in g.edges if e.src == brk.id)

    def test_empty_loop_body(self):
        g = graph_of("void f() { while (c) { } a(); }")
        dec = next(n for n in g.nodes if n.kind == "decision")
        out = [e for e in g.edges if e.src == dec.id and e.label == "нет"]
        assert out, "empty loop must still have a no-exit"


# ------------------------------------------------------------------ 4. switch
class TestSwitch:
    def test_switch_default_and_fallthrough(self):
        src = """
        void f(int x) {
            switch (x) {
                case 1: a(); break;
                case 2: b();
                case 3: c(); break;
                default: d();
            }
            e();
        }
        """
        g = graph_of(src)
        b_node = next(n for n in g.nodes if n.text == "b()")
        c_node = next(n for n in g.nodes if n.text == "c()")
        assert any(e.src == b_node.id and e.dst == c_node.id for e in g.edges)

    def test_switch_without_default(self):
        src = "void f(int x) { switch (x) { case 1: a(); break; } b(); }"
        g = graph_of(src)
        b_node = next(n for n in g.nodes if n.text == "b()")
        sw = next(n for n in g.nodes if n.kind == "decision")
        assert any(e.src == sw.id and e.dst == b_node.id for e in g.edges)


# ------------------------------------------------------------------ 5. texts
class TestTexts:
    def test_no_datatypes_but_markers(self):
        src = """
        int process(int *data, int &result) {
            int x = 1;
            double result2 = 0.5;
            return x;
        }
        """
        g = graph_of(src, "process")
        io = next(n for n in g.nodes if n.kind == "io")
        assert io.text == "Ввод: *data, &result"
        texts = [n.text for n in g.nodes]
        assert "x = 1" in texts
        assert "result2 = 0.5" in texts
        assert not any(t.startswith("int ") or t.startswith("double ")
                       for t in texts)

    def test_main_terminators(self):
        g = graph_of("int main() { a(); }", "main")
        texts = [n.text for n in g.nodes]
        assert "Начало" in texts
        assert "Конец" in texts

    def test_subroutine_terminator_is_its_name(self):
        g = graph_of("void helper() { a(); }", "helper")
        texts = [n.text for n in g.nodes]
        assert "helper" in texts
        assert "Начало" not in texts

    def test_output_blocks_present(self):
        src = 'void f() { cout << "error: " << x << endl; }'
        g = graph_of(src)
        io = next(n for n in g.nodes if n.kind == "io")
        assert io.text.startswith("Вывод:")
        assert "error" in io.text

    def test_main_sorts_first_multiple_functions(self):
        src = """
        double calc(double a) { return a * 2; }
        void log_it() { cout << "ok"; }
        int main() { calc(1); log_it(); return 0; }
        """
        gs = build_graphs(parse_cpp(src))
        assert gs[0].name == "main"
        assert len(gs) == 3


# ------------------------------------------------------------------ 6. errors
class TestErrors:
    def test_goto_rejected(self):
        with pytest.raises(ParseError) as exc:
            parse_cpp("int main() { goto lbl; lbl: return 0; }")
        assert "goto" in str(exc.value)

    def test_try_rejected(self):
        with pytest.raises(ParseError):
            parse_cpp("int main() { try { a(); } catch (...) { } }")

    def test_syntax_error_has_line(self):
        with pytest.raises(ParseError) as exc:
            parse_cpp("int main() {\n  while (\n}")
        assert exc.value.line >= 1


# ------------------------------------------------------------------ 7. geometry
def _overlaps(g: LGraph):
    bad = []
    ns = [n for n in g.nodes if n.kind != "merge"]  # merge anchors invisible
    for i in range(len(ns)):
        for j in range(i + 1, len(ns)):
            a, b = ns[i], ns[j]
            if (a.x < b.x + b.w and b.x < a.x + a.w
                    and a.y < b.y + b.h and b.y < a.y + a.h):
                bad.append((a, b))
    return bad


def _seg_intersects_rect(x0, y0, x1, y1, bx0, by0, bx1, by1) -> bool:
    """Liang-Barsky: does the segment pass through the rect interior?"""
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - bx0, bx1 - x0, y0 - by0, by1 - y0)
    t0, t1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-9:
            if qi < 0:
                return False
            continue
        t = qi / pi
        if pi < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 < t1 - 1e-6


def _line_hits_blocks(g: LGraph):
    """Edge segments passing through foreign node boxes (borders touch ok)."""
    bad = []
    pad = 2.5
    for e in g.edges:
        pts = e.points
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            for n in g.nodes:
                if n.kind in ("merge",):
                    continue
                # skip the nodes this edge connects to (the old check
                # skipped *every* node for the last segment of an edge,
                # hiding lines that enter their target through a block)
                if n.id in (e.src, e.dst):
                    continue
                if _seg_intersects_rect(
                    x0, y0, x1, y1,
                    n.x + pad, n.y + pad, n.x + n.w - pad, n.y + n.h - pad,
                ):
                    bad.append((pts, i, n))
    return bad


def _seg_overlap_1d(a0, a1, b0, b1):
    """Length of the overlap of two 1D segments (0 if just touching)."""
    lo = max(min(a0, a1), min(b0, b1))
    hi = min(max(a0, a1), max(b0, b1))
    return max(0.0, hi - lo)


def _segs_overlap(p0, p1, q0, q1) -> bool:
    """True if two axis-aligned segments run on top of each other.

    Crossings at a single point are fine; sharing a stretch of line is
    an edge-on-edge overlap. A small tolerance ignores endpoint touches.
    """
    (x0, y0), (x1, y1) = p0, p1
    (x2, y2), (x3, y3) = q0, q1
    horiz_p, horiz_q = abs(y1 - y0) < 1e-6, abs(y3 - y2) < 1e-6
    if horiz_p and horiz_q:
        if abs(y0 - y2) > 3.0:
            return False
        return _seg_overlap_1d(x0, x1, x2, x3) > 4.0
    if not horiz_p and not horiz_q:
        if abs(x0 - x2) > 3.0:
            return False
        return _seg_overlap_1d(y0, y1, y2, y3) > 4.0
    return False


def _edge_overlaps(g: LGraph):
    """Pairs of edges whose segments run on top of each other.

    Joining the same vertical drop into a shared junction point is
    legal (branch merge): skip pairs whose only common stretch ends at
    a shared endpoint of both edges.
    """
    bad = []
    es = g.edges
    for i in range(len(es)):
        for j in range(i + 1, len(es)):
            a, b = es[i].points, es[j].points
            # shared endpoints (same junction point) are fine
            shared = {
                (round(x), round(y)) for x, y in a
            } & {
                (round(x), round(y)) for x, y in b
            }
            if not shared:
                continue  # unrelated lines sharing a corridor: real overlap
            for k in range(len(a) - 1):
                for m in range(len(b) - 1):
                    if _segs_overlap(a[k], a[k + 1], b[m], b[m + 1]):
                        seg_mid = (
                            (a[k][0] + a[k + 1][0]) / 2,
                            (a[k][1] + a[k + 1][1]) / 2,
                        )
                        if any(
                            abs(seg_mid[0] - sx) < 3
                            and abs(seg_mid[1] - sy) < 3
                            for sx, sy in shared
                        ):
                            continue
                        # same-junction merge: the shared stretch must run
                        # into one common endpoint of both edges
                        ends_a = {
                            (round(a[0][0]), round(a[0][1])),
                            (round(a[-1][0]), round(a[-1][1])),
                        }
                        ends_b = {
                            (round(b[0][0]), round(b[0][1])),
                            (round(b[-1][0]), round(b[-1][1])),
                        }
                        if shared & ends_a & ends_b:
                            continue
                        bad.append((i, j, k, m))
    return bad


GEOMETRY_SOURCES = [
    'int main() { int n; cin >> n; int s = 0; '
    'for (int i = 0; i <= n; i++) { s += i; } '
    'if (s > 100) cout << "big"; else cout << "small"; }',
    'void f() { while (a) { if (b) continue; if (c) break; x(); } y(); }',
    'void f() { do { a(); } while (c); b(); }',
    'void g(int *d, int &r) { r = *d; } int main() { int v; g(&v, v); }',
]

_COMPLEX_PATH = (
    Path(__file__).resolve().parent.parent / "examples" / "complex.cpp"
)
GEOMETRY_COMPLEX = (
    [_COMPLEX_PATH.read_text(encoding="utf-8")]
    if _COMPLEX_PATH.exists() else []
)

_EXAMPLES = sorted(
    (Path(__file__).resolve().parent.parent / "examples").glob("*.cpp")
)

# regression sources for the routing fixes
ROUTING_SOURCES = [
    # back edge of the outer loop used to enter the counter block through
    # the "да" block of the early-return branch beside it
    'int main() { int n; cin >> n; if (n < 1) { cout << "bad"; return 0; } '
    'for (int i = 0; i < n; i++) { for (int j = 0; j < n; j++) '
    '{ a(i, j); b(j); } c(); } d(); return 0; }',
    # break used to drop straight through the continue/loop-back junction
    'int main() { int k = 5; while (k > 0) { k--; if (k == 2) continue; '
    'if (k == 1) break; } return 0; }',
    # do-while + while: back edges and "нет" exits used to cross and run
    # 2px apart into the same condition
    'int main() { int k = 0; do { k++; } while (k < 3); '
    'while (k > 0) { k--; if (k == 2) continue; if (k == 1) break; } '
    'switch (k) { case 0: x(); break; case 1: y(); break; '
    'default: z(); } return 0; }',
    # three nested counters in a side column: needs a wider column gap
    'int main() { int n; cin >> n; if (n < 0) { cout << "neg"; return 0; } '
    'for (int i = 0; i < n; i++) { for (int j = 0; j < n; j++) '
    '{ for (int k = 0; k < n; k++) { a(i, j, k); } } } return 0; }',
] + [p.read_text(encoding="utf-8") for p in _EXAMPLES]


class TestRouting:
    """Lines never run through blocks/junctions or on top of each other."""

    @pytest.mark.parametrize("src", ROUTING_SOURCES)
    def test_no_line_through_blocks(self, src):
        from geometry_check import node_hits
        for g in convert(src):
            assert not node_hits(g)
            assert not _line_hits_blocks(g)

    @pytest.mark.parametrize("src", ROUTING_SOURCES)
    def test_no_lines_on_top_of_each_other(self, src):
        from geometry_check import edge_overlaps
        for g in convert(src):
            assert not edge_overlaps(g)

    @pytest.mark.parametrize("src", ROUTING_SOURCES)
    def test_no_block_overlaps(self, src):
        for g in convert(src):
            assert not _overlaps(g)

    def test_loop_back_edge_left_exit_right(self):
        g = layout_of("void f() { while (c) { a(); } b(); }")
        dec = next(n for n in g.nodes if n.kind == "decision")
        back = next(e for e in g.edges if e.dst == dec.id
                    and e.arrow == "always")
        exit_ = next(e for e in g.edges if e.src == dec.id
                     and e.label == "нет")
        assert min(x for x, _ in back.points) < dec.x
        assert max(x for x, _ in exit_.points) > dec.x + dec.w


class TestGeometry:
    @pytest.mark.parametrize("src", GEOMETRY_SOURCES)
    def test_no_node_overlaps(self, src):
        for g in convert(src):
            assert not _overlaps(g), [
                (a.kind, a.lines, b.kind, b.lines) for a, b in _overlaps(g)
            ]

    @pytest.mark.parametrize("src", GEOMETRY_SOURCES)
    def test_lines_do_not_cross_blocks(self, src):
        for g in convert(src):
            bad = _line_hits_blocks(g)
            assert not bad, [
                (pts, n.kind, n.lines) for pts, _, n in bad
            ]

    @pytest.mark.parametrize("src", GEOMETRY_SOURCES)
    def test_labels_off_blocks(self, src):
        for g in convert(src):
            for e in g.edges:
                if not e.label:
                    continue
                for n in g.nodes:
                    if n.kind == "merge":
                        continue
                    if (n.x + 4 < e.lx < n.x + n.w - 4
                            and n.y + 4 < e.ly < n.y + n.h - 4):
                        pytest.fail(
                            f"label {e.label!r} overlaps {n.kind} {n.lines}"
                        )

    @pytest.mark.parametrize("src", GEOMETRY_SOURCES)
    def test_layout_heights_sane(self, src):
        for g in convert(src):
            # regression: runaway y inflation
            assert g.height < 4000, f"height {g.height} too large"

    @pytest.mark.parametrize("src", GEOMETRY_SOURCES + GEOMETRY_COMPLEX)
    def test_edges_do_not_overlap_each_other(self, src):
        for g in convert(src):
            bad = _edge_overlaps(g)
            assert not bad, [
                (g.edges[i].points, g.edges[j].points)
                for i, j, _, _ in bad
            ]

    @pytest.mark.parametrize("src", GEOMETRY_COMPLEX)
    def test_complex_stays_compact(self, src):
        for g in convert(src):
            assert g.height < 4000, f"{g.name}: height {g.height} too large"
            assert not _overlaps(g)
            assert not _line_hits_blocks(g)
            assert not _edge_overlaps(g)


