"""Flowchart graph, layout and SVG rendering tests."""

import xml.etree.ElementTree as ET

from flowchart.convert import convert, convert_to_svg
from flowchart.graph import build_graphs
from flowchart.parser import parse_cpp


def graph_of(src):
    return build_graphs(parse_cpp(src))[0]


def node_texts(g):
    return [n.text for n in g.nodes]


class TestGraph:
    def test_straight_line(self):
        g = graph_of("void f() { a = 1; b = 2; }")
        # start -> a -> b -> end
        chain = [e for e in g.edges if e.down]
        assert len(chain) == 3

    def test_if_branches(self):
        g = graph_of("void f() { if (c) a(); else b(); }")
        dec = [n for n in g.nodes if n.kind == "decision"]
        assert len(dec) == 1
        out_edges = [e for e in g.edges if e.src == dec[0].id]
        labels = {e.label for e in out_edges}
        assert labels == {"да", "нет"}
        # else branch sits one column to the right
        io_nodes = [n for n in g.nodes if n.kind == "process"]
        cols = {n.text: n.col for n in io_nodes}
        assert cols["a()"] == 0
        assert cols["b()"] == 1

    def test_while_loop_back(self):
        g = graph_of("void f() { while (c) a(); }")
        dec = next(n for n in g.nodes if n.kind == "decision")
        # body flows down from the condition; the back edge joins the
        # entry line above the condition (GOST: not into the diamond)
        down = [e for e in g.edges if e.src == dec.id and e.src_port == "b"]
        back = [
            e for e in g.edges
            if e.dst == dec.id and e.dst_port == "t" and not e.down
        ]
        assert len(down) == 1 and len(back) == 1

    def test_break_exits_loop(self):
        g = graph_of("void f() { while (c) { if (d) break; a(); } b(); }")
        brk = next(n for n in g.nodes if n.text == "break")
        # break flows to the first statement after the loop
        targets = {e.dst for e in g.edges if e.src == brk.id}
        assert len(targets) == 1
        dst = next(n for n in g.nodes if n.id == next(iter(targets)))
        assert dst.text == "b()"

    def test_continue_returns_to_condition(self):
        g = graph_of("void f() { while (c) { if (d) continue; a(); } }")
        cont = next(n for n in g.nodes if n.text == "continue")
        dec = next(n for n in g.nodes if n.kind == "decision")
        # continue may first join a shared junction with the other
        # loop-back tail (so the two don't draw overlapping back edges),
        # but it must still reach the condition eventually
        seen = {cont.id}
        frontier = {cont.id}
        while frontier:
            frontier = {e.dst for e in g.edges if e.src in frontier} - seen
            seen |= frontier
        assert dec.id in seen

    def test_switch_columns(self):
        src = """
        void f(int x) {
            switch (x) {
                case 1: a(); break;
                case 2: b(); break;
            }
        }
        """
        g = graph_of(src)
        by_text = {n.text: n.col for n in g.nodes}
        assert by_text["a()"] == 1
        assert by_text["b()"] == 2

    def test_return_goes_to_return_terminator(self):
        g = graph_of("void f() { g(); return 1; }")
        ret = next(n for n in g.nodes if n.text.startswith("return"))
        edges = [e for e in g.edges if e.src == ret.id]
        assert len(edges) == 1
        assert edges[0].dst == g.ret

    def test_main_hides_return(self):
        g = graph_of("int main() { a = 1; return 0; }")
        texts = node_texts(g)
        assert not any(t.startswith("return") for t in texts)
        assert "Начало" in texts and "Конец" in texts
        # unused "Возврат" terminator is hidden
        ret_node = next(n for n in g.nodes if n.id == g.ret)
        assert ret_node.kind == "skip"

    def test_subroutine_params_become_input(self):
        g = graph_of("int add(int a, int b) { return a + b; }")
        io = next(n for n in g.nodes if n.kind == "io")
        assert io.text == "Ввод: a, b"
        assert io.col == 0

    def test_user_call_is_predefined_process(self):
        src = "void helper() {} void f() { helper(); }"
        prog = parse_cpp(src)
        from flowchart.graph import build_graphs
        gs = build_graphs(prog)
        f = next(g for g in gs if g.name == "f")
        call = next(n for n in f.nodes if n.text.startswith("helper"))
        assert call.kind == "predef"

    def test_main_sorts_first(self):
        src = "void helper() {} int main() { return 0; }"
        from flowchart.graph import build_graphs
        gs = build_graphs(parse_cpp(src))
        assert [g.name for g in gs] == ["main", "helper"]


def _overlaps(g):
    bad = []
    ns = g.nodes
    for i in range(len(ns)):
        for j in range(i + 1, len(ns)):
            a, b = ns[i], ns[j]
            if (a.x < b.x + b.w and b.x < a.x + a.w
                    and a.y < b.y + b.h and b.y < a.y + a.h):
                bad.append((a, b))
    return bad


DEMO = """
#include <iostream>
using namespace std;
int main() {
    int n, sum = 0;
    cin >> n;
    for (int i = 1; i <= n; i++) sum += i;
    if (sum > 100) cout << "big" << endl;
    else cout << "small" << endl;
    int k = 0;
    do { k++; } while (k < 3);
    while (k > 0) { k--; if (k == 2) continue; if (k == 1) break; }
    switch (k) {
        case 0: cout << "zero"; break;
        case 1: cout << "one"; break;
        default: cout << "other";
    }
    return 0;
}
"""


class TestLayout:
    def test_no_node_overlaps_demo(self):
        g = convert(DEMO)[0]
        assert not _overlaps(g), [
            (a.id, a.lines, b.id, b.lines) for a, b in _overlaps(g)
        ]

    def test_end_is_lowest(self):
        g = convert(DEMO)[0]
        end = next(n for n in g.nodes if n.id == g.end)
        # exit connectors (break/...) drain straight to the end marker and
        # are allowed to sit beside the tail of the last case column
        exits = {
            n.id for n in g.nodes
            if n.kind == "connector" and n.lines == ["break"]
        }
        bottom = max(
            n.y + n.h for n in g.nodes
            if n.id not in (g.start, g.end) and n.id not in exits
        )
        assert end.y >= bottom

    def test_edges_have_points(self):
        for g in convert(DEMO):
            for e in g.edges:
                assert len(e.points) >= 2


class TestSvg:
    def test_valid_xml(self):
        root = ET.fromstring(convert_to_svg(DEMO))
        assert root.tag.endswith("svg")

    def test_contains_nodes_and_arrows(self):
        svg = convert_to_svg(DEMO)
        assert "Ввод: n" in svg
        assert "arrow" in svg
        assert "<polygon" in svg  # decisions / io present

    def test_empty_program(self):
        root = ET.fromstring(convert_to_svg("// nothing"))
        assert root.tag.endswith("svg")
