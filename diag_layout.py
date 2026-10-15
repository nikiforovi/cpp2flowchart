"""Temporary diagnostics for layout issues (removed after debugging)."""

import sys

from flowchart.convert import convert


def dump(src_path: str) -> None:
    src = open(src_path, encoding="utf-8").read()
    for lg in convert(src):
        print(f"=== {lg.name}: {len(lg.nodes)} nodes, {len(lg.edges)} edges, "
              f"w={lg.width:.0f} h={lg.height:.0f}")
        for n in lg.nodes:
            print(f"  N{n.id:2d} {n.kind:9s} x={n.x:7.1f} y={n.y:7.1f} "
                  f"w={n.w:6.1f} h={n.h:5.1f} {n.lines}")
        for i, e in enumerate(lg.edges):
            pts = " ".join(f"({px:.0f},{py:.0f})" for px, py in e.points)
            print(f"  E{i:2d} {pts} lbl={e.label!r} arrow={e.arrow}")


if __name__ == "__main__":
    dump(sys.argv[1] if len(sys.argv) > 1 else "examples/complex.cpp")
