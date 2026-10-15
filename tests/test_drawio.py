"""draw.io export: well-formed mxfile, cells consistent with the layout."""

import xml.etree.ElementTree as ET
from pathlib import Path

import main as cli
from flowchart.convert import convert, convert_to_drawio

COMPLEX = (Path(__file__).resolve().parent.parent
           / "examples" / "complex.cpp").read_text(encoding="utf-8")


def _pages(doc: str):
    root = ET.fromstring(doc)
    assert root.tag == "mxfile"
    return root.findall("diagram")


def test_one_page_per_function():
    pages = _pages(convert_to_drawio(COMPLEX))
    assert [p.get("name") for p in pages] == ["main", "findIndices"]
    assert len({p.get("id") for p in pages}) == 2


def test_cells_match_layout():
    graphs = convert(COMPLEX)
    for g, page in zip(graphs, _pages(convert_to_drawio(COMPLEX))):
        cells = page.find("mxGraphModel/root").findall("mxCell")
        ids = [c.get("id") for c in cells]
        assert len(ids) == len(set(ids)), "cell ids must be unique"
        vertices = {c.get("id"): c for c in cells
                    if c.get("vertex") == "1"
                    and "edgeLabel" not in c.get("style", "")}
        edges = [c for c in cells if c.get("edge") == "1"]
        visible = [n for n in g.nodes if n.kind != "merge"]
        assert len(vertices) == len(visible)
        assert len(edges) == len(g.edges)
        for c in edges:
            for end in ("source", "target"):
                if c.get(end) is not None:
                    assert c.get(end) in vertices
            geo = c.find("mxGeometry")
            roles = {p.get("as") for p in geo.findall("mxPoint")}
            assert {"sourcePoint", "targetPoint"} <= roles


def test_edge_route_preserved():
    g = convert(COMPLEX)[0]
    page = _pages(convert_to_drawio(COMPLEX))[0]
    cells = {c.get("id"): c for c in page.iter("mxCell")}
    for i, e in enumerate(g.edges):
        geo = cells[f"e{i}"].find("mxGeometry")
        arr = geo.find("Array")
        mids = [] if arr is None else [
            (float(p.get("x")), float(p.get("y")))
            for p in arr.findall("mxPoint")
        ]
        assert len(mids) == len(e.points) - 2


def test_merge_junctions_are_not_cells():
    src = "void f() { if (a) x(); else y(); z(); }"
    g = convert(src)[0]
    merges = {n.id for n in g.nodes if n.kind == "merge"}
    assert merges
    doc = convert_to_drawio(src)
    ids = {c.get("id") for c in ET.fromstring(doc).iter("mxCell")}
    assert not any(f"n{m}" in ids for m in merges)


def test_text_is_escaped_and_labels_attached():
    src = 'int main() { int a; if (a < 3 && a > 0) cout << "<&>"; }'
    doc = convert_to_drawio(src)
    cells = list(ET.fromstring(doc).iter("mxCell"))
    values = [c.get("value") or "" for c in cells]
    # value is HTML (html=1): user text is HTML-escaped inside it
    assert any("a &lt; 3 &amp;&amp; a &gt; 0" in v for v in values)
    labels = [c for c in cells if "edgeLabel" in (c.get("style") or "")]
    assert {c.get("value") for c in labels} >= {"да", "нет"}
    edge_ids = {c.get("id") for c in cells if c.get("edge") == "1"}
    assert all(c.get("parent") in edge_ids for c in labels)


def test_cli_drawio_by_extension(tmp_path: Path):
    src = tmp_path / "prog.cpp"
    src.write_text("int main() { return 0; }", encoding="utf-8")
    dst = tmp_path / "out.drawio"
    assert cli.main([str(src), "-o", str(dst)]) == 0
    assert ET.fromstring(dst.read_text(encoding="utf-8")).tag == "mxfile"


def test_cli_drawio_by_flag(tmp_path: Path):
    src = tmp_path / "prog.cpp"
    src.write_text("int main() { return 0; }", encoding="utf-8")
    assert cli.main([str(src), "-f", "drawio"]) == 0
    assert (tmp_path / "prog.drawio").exists()
