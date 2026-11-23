# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: CLI app (c2fc)."""

import os
import sys

from PyInstaller.config import CONF

# Keep platform builds apart: dist/linux/c2fc, dist/win/c2fc.exe (README).
# Without this PyInstaller drops the single-file executable straight into
# dist/ and a Windows build would overwrite the Linux one.
_PLATFORM_DIR = {"win32": "win", "darwin": "macos"}.get(sys.platform, "linux")
if os.path.basename(os.path.normpath(CONF["distpath"])) != _PLATFORM_DIR:
    CONF["distpath"] = os.path.join(CONF["distpath"], _PLATFORM_DIR)

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
