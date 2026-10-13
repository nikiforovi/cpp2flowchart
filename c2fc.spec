# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: GUI app (c2fc-gui)."""

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "tree_sitter",
        "tree_sitter_cpp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="c2fc-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
