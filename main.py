#!/usr/bin/env python3
"""CLI: convert a C++ file into an SVG flowchart."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flowchart.convert import ParseError, convert_to_svg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="c2fc",
        description="Конвертер C++ в блок-схему (SVG).",
    )
    ap.add_argument("input", help="путь к .cpp файлу")
    ap.add_argument("-o", "--output",
                    help="путь к выходному .svg (по умолчанию: рядом с входом)")
    args = ap.parse_args(argv)

    src_path = Path(args.input)
    try:
        source = src_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"не удалось прочитать файл: {exc}", file=sys.stderr)
        return 1

    try:
        svg = convert_to_svg(source)
    except ParseError as exc:
        print(f"ошибка парсинга (строка {exc.line}): {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.output) if args.output else src_path.with_suffix(".svg")
    out_path.write_text(svg, encoding="utf-8")
    print(f"схема сохранена: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
