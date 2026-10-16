"""Regressions for abrupt exits and control-flow entry points."""

import xml.etree.ElementTree as ET

import pytest

from flowchart.convert import convert_to_drawio, convert_to_svg
from flowchart.graph import build_graphs
from flowchart.parser import parse_cpp


def graph_of(body):
    return build_graphs(parse_cpp(f"void f() {{ {body} }}"))[0]


def node(g, text):
    return next(n for n in g.nodes if n.text == text)


def assert_reachable(g):
    seen = {g.start}
    frontier = seen.copy()
    while frontier:
        frontier = {e.dst for e in g.edges if e.src in frontier} - seen
        seen |= frontier
    assert {n.id for n in g.nodes if n.kind != "skip"} <= seen
    assert not any(g.nodes[e.dst].kind == "skip" for e in g.edges)


@pytest.mark.parametrize("body", [
    "return; dead();",
    "if (c) return; else return; dead();",
    "while (c) { break; dead(); } after();",
    "while (c) { continue; dead(); } after();",
    "for (int i = 0; i < 3; ++i) { break; dead(); } after();",
    "for (int i = 0; i < 3; ++i) { continue; dead(); } after();",
    "switch (x) { case 1: return; default: return; } dead();",
    "do { return; } while (c); dead();",
    "do { break; dead(); } while (c); after();",
])
def test_abrupt_exit_does_not_create_unreachable_nodes(body):
    g = graph_of(body)
    assert "dead()" not in [n.text for n in g.nodes]
    assert_reachable(g)


@pytest.mark.parametrize("body", ["{}", ";"])
def test_empty_do_while_has_both_branches(body):
    g = graph_of(f"do {body} while (c); after();")
    dec = node(g, "c")
    edges = [e for e in g.edges if e.src == dec.id]
    assert {e.label for e in edges} == {"да", "нет"}
    back = next(e for e in edges if e.label == "да")
    assert back.dst == dec.id and not back.down
    assert next(e for e in edges if e.label == "нет").dst == node(g, "after()").id
    assert_reachable(g)


@pytest.mark.parametrize("body", [
    "if (c) a(); else b();",
    "if (c) return; else b();",
    "do { if (c) a(); else b(); } while (inner);",
])
def test_do_while_repeats_from_actual_body_entry(body):
    g = graph_of(f"do {{ {body} }} while (again); after();")
    dec = node(g, "again")
    back = next(e for e in g.edges if e.src == dec.id and e.label == "да")
    assert back.dst == node(g, "c").id
    assert not back.down
    assert_reachable(g)


@pytest.mark.parametrize("body", ["return;", "break;", "if (c) return; else break;"])
def test_do_while_does_not_evaluate_condition_after_unconditional_exit(body):
    g = graph_of(f"do {{ {body} }} while (unreached);")
    assert "unreached" not in [n.text for n in g.nodes]
    assert_reachable(g)


def test_do_while_preserves_nested_loop_exit_label():
    g = graph_of("do { while (inner) a(); } while (outer);")
    edge = next(e for e in g.edges
                if e.src == node(g, "inner").id and e.dst == node(g, "outer").id)
    assert edge.label == "нет"


def test_switch_fallthrough_enters_condition_not_merge():
    g = graph_of("""
        switch (x) {
            case 1: a();
            case 2:
            case 3: if (c) b(); else d(); break;
        }
    """)
    first = node(g, "c")
    assert any(e.src == node(g, "a()").id and e.dst == first.id for e in g.edges)
    bus = next(e.dst for e in g.edges
               if e.src == node(g, "x").id and g.nodes[e.dst].kind == "merge")
    assert any(e.src == bus and e.dst == first.id and e.label == "2"
               for e in g.edges)
    assert_reachable(g)


@pytest.mark.parametrize("render", [convert_to_svg, convert_to_drawio])
@pytest.mark.parametrize("body", [
    "do {} while (c);",
    "do { if (c) return; else b(); } while (again);",
    "switch (x) { case 1: return; default: return; } dead();",
])
def test_control_flow_regressions_render_in_both_formats(render, body):
    ET.fromstring(render(f"void f() {{ {body} }}"))
