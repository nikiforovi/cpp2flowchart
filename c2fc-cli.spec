# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: CLI app (c2fc)."""

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "tree_sitter",
        "tree_sitter_cpp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="c2fc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
