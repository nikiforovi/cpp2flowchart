#!/usr/bin/env python3
"""CLI: convert a C++ file into a flowchart (SVG or draw.io)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flowchart.convert import ParseError, convert_to_drawio, convert_to_svg

FORMATS = {"svg": (".svg", convert_to_svg),
           "drawio": (".drawio", convert_to_drawio)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="c2fc",
        description="Конвертер C++ в блок-схему (SVG или draw.io).",
    )
    ap.add_argument("input", help="путь к .cpp файлу")
    ap.add_argument("-o", "--output",
                    help="путь к выходному файлу (по умолчанию: рядом с "
                         "входом, расширение по формату)")
    ap.add_argument("-f", "--format", choices=sorted(FORMATS),
                    help="формат вывода; по умолчанию — по расширению "
                         "--output (.drawio/.xml -> drawio), иначе svg")
    args = ap.parse_args(argv)

    fmt = args.format
    if fmt is None:
        suffix = Path(args.output).suffix.lower() if args.output else ""
        fmt = "drawio" if suffix in (".drawio", ".xml") else "svg"
    ext, render = FORMATS[fmt]

    src_path = Path(args.input)
    try:
        source = src_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"не удалось прочитать файл: {exc}", file=sys.stderr)
        return 1

    try:
        doc = render(source)
    except ParseError as exc:
        print(f"ошибка парсинга (строка {exc.line}): {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.output) if args.output else src_path.with_suffix(ext)
    try:
        out_path.write_text(doc, encoding="utf-8")
    except OSError as exc:
        print(f"не удалось сохранить файл: {exc}", file=sys.stderr)
        return 1
    print(f"схема сохранена: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
