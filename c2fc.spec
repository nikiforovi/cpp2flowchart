# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: GUI app (c2fc-gui)."""

import os
import sys

from PyInstaller.config import CONF
from PyInstaller.utils.hooks.qt import pyqt6_library_info

# Keep platform builds apart: dist/linux/c2fc-gui, dist/win/c2fc-gui.exe.
# Without this PyInstaller drops the single-file executable straight into
# dist/ and a Windows build would overwrite the Linux one.
_PLATFORM_DIR = {"win32": "win", "darwin": "macos"}.get(sys.platform, "linux")
if os.path.basename(os.path.normpath(CONF["distpath"])) != _PLATFORM_DIR:
    CONF["distpath"] = os.path.join(CONF["distpath"], _PLATFORM_DIR)

# PyInstaller's hook-PyQt6.py collects the Qt binaries, the plugins
# (platforms/qwindows.dll, imageformats, styles, ...), the runtime hook and the
# 'pkgutil'/'PyQt6.sip' hidden imports only when PyQt6 is importable in the
# *build* environment. When it is not (e.g. a Wine prefix where Qt >= 6.10
# cannot load because Wine has no icuuc.dll), the hook silently does nothing and
# the resulting .exe dies at startup with "No module named 'pkgutil'" or
# "could not find or load the Qt platform plugin windows". Fail loudly instead.
if pyqt6_library_info.version is None:
    raise SystemExit(
        "PyQt6 is not importable in the build environment "
        "(`python -c \"import PyQt6.QtCore\"` must work), therefore PyInstaller "
        "would not bundle Qt plugins nor the 'pkgutil' module and the .exe "
        "would be broken. See README, section 'Сборка бинарников'."
    )

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6/__init__.py does `__import__('pkgutil')`; also required by
        # PyInstaller's own runtime hook for pkgutil.iter_modules().
        "pkgutil",
        "PyQt6.sip",
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
