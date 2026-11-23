"""Arrow-head placement regressions.

Two rendering defects made the layout read like a broken polyline:

* several flows joining the same junction each drew an arrow head on the
  same point (the overlapping triangles turned into a black blob);
* a loop-back edge joined the approach line 16 px above the target while
  the approach itself turned into the block 18 px above it, so the head
  sat 2 px from that corner - the arrow looked like it was stuck in the
  middle of a bent line.
"""

from pathlib import Path

import pytest

from flowchart.convert import convert
from flowchart.layout import edge_arrow

HERE = Path(__file__).resolve().parent
EXAMPLES = sorted((HERE.parent / "examples").glob("*.cpp"))

MIN_CLEAR = 6.0  # a head this close to a corner reads as a broken line

# do-while + while + switch: the sample that exposes both defects
LOOPS_AND_SWITCH = """
int main() {
    int k = 0;
    do { k++; } while (k < 3);
    while (k > 0) {
        k--;
        if (k == 2) continue;
        if (k == 1) break;
    }
    switch (k) {
        case 0: cout << "zero" << endl; break;
        case 1: cout << "one" << endl; break;
        default: cout << "other" << endl;
    }
    return 0;
}
"""

SOURCES = [p.read_text(encoding="utf-8") for p in EXAMPLES]
SOURCES += [
    LOOPS_AND_SWITCH,
    "void f() { while (c) { a(); } b(); }",
    "void f() { do { a(); } while (c); b(); }",
    "void f() { if (a) { if (b) x(); else y(); } else z(); w(); }",
]


def _tips(g):
    """(edge index, edge) of every edge that gets a drawn arrow head."""
    return [
        (i, e) for i, e in enumerate(g.edges)
        if len(e.points) >= 2 and edge_arrow(e.points, e.arrow)
    ]


def _on_segment(pt, a, b) -> bool:
    if abs(a[0] - b[0]) < 0.5:
        return (abs(pt[0] - a[0]) < 0.5
                and min(a[1], b[1]) - 0.5 <= pt[1] <= max(a[1], b[1]) + 0.5)
    if abs(a[1] - b[1]) < 0.5:
        return (abs(pt[1] - a[1]) < 0.5
                and min(a[0], b[0]) - 0.5 <= pt[0] <= max(a[0], b[0]) + 0.5)
    return False


@pytest.mark.parametrize("src", SOURCES)
def test_arrow_heads_do_not_stack(src):
    """One junction point gets at most one arrow head."""
    for g in convert(src):
        seen: dict[tuple[float, float], int] = {}
        for i, e in _tips(g):
            tip = (round(e.points[-1][0], 1), round(e.points[-1][1], 1))
            assert tip not in seen, (
                f"{g.name}: arrow heads of E{seen[tip]} and E{i} "
                f"overlap at {tip}"
            )
            seen[tip] = i


@pytest.mark.parametrize("src", SOURCES)
def test_arrow_heads_clear_of_corners(src):
    """A head landing on another line must not hit its bend."""
    for g in convert(src):
        for i, e in _tips(g):
            tip = e.points[-1]
            for j, f in enumerate(g.edges):
                if j == i or len(f.points) < 2:
                    continue
                for a, b in zip(f.points, f.points[1:]):
                    if not _on_segment(tip, a, b):
                        continue
                    near = min(
                        abs(tip[0] - a[0]) + abs(tip[1] - a[1]),
                        abs(tip[0] - b[0]) + abs(tip[1] - b[1]),
                    )
                    # exactly on the junction is fine (T-junction), just
                    # not a few pixels away from the corner
                    assert near == 0 or near >= MIN_CLEAR, (
                        f"{g.name}: E{i} head at {tip} sits {near:.1f}px "
                        f"from the corner {a}->{b} of E{j}"
                    )
