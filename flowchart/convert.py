"""High-level conversion pipeline: C++ source -> layout graphs / SVG."""

from __future__ import annotations

from .parser import ParseError, parse_cpp
from .graph import build_graphs
from .layout import LGraph, layout_all
from .svg import render_svg

__all__ = ["ParseError", "convert", "convert_to_svg"]


def convert(source: str) -> list[LGraph]:
    """Parse C++ source and lay out one flowchart per function."""
    return layout_all(build_graphs(parse_cpp(source)))


def convert_to_svg(source: str) -> str:
    """Convert C++ source into a single SVG document."""
    return render_svg(convert(source))
