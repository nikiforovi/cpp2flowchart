#!/bin/bash
# Wrapper script for gui.py that fixes PyQt6/system Qt library conflicts.
#
# If system Qt libraries are installed (e.g., ubuntu qt6-base), PyQt6 may fail
# with "undefined symbol ... Qt_6_PRIVATE_API". This script adds PyQt6's bundled
# Qt libraries to LD_LIBRARY_PATH before launching Python.

set -e

# Find the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python executable (prefer the one used to install dependencies)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON="python3"
fi

# Get Python version to construct the correct path
PYTHON_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

# Construct the path to PyQt6's bundled Qt libraries
PYQT6_QT_LIB="$SCRIPT_DIR/.venv/lib/python${PYTHON_VERSION}/site-packages/PyQt6/Qt6/lib"

# If PyQt6 is installed system-wide, try that path too
if [ ! -d "$PYQT6_QT_LIB" ]; then
    # Try to find it via Python import
    PYQT6_QT_LIB=$("$PYTHON" -c "
import sys
from pathlib import Path
try:
    import PyQt6
    lib_path = Path(PyQt6.__file__).parent / 'Qt6' / 'lib'
    if lib_path.exists():
        print(lib_path)
        sys.exit(0)
except ImportError:
    pass
print('')
" 2>/dev/null || echo "")
fi

# Set LD_LIBRARY_PATH if PyQt6 lib path was found
if [ -n "$PYQT6_QT_LIB" ] && [ -d "$PYQT6_QT_LIB" ]; then
    export LD_LIBRARY_PATH="${PYQT6_QT_LIB}:${LD_LIBRARY_PATH}"
fi

# Launch gui.py
cd "$SCRIPT_DIR"

# Workaround: GNOME 46 moved antialiasing/hinting keys to the
# org.gnome.settings-daemon.plugins.xsettings.deprecated schema, but GTK3
# (loaded via Qt's qgtk3 platform theme) still reads them from the main
# schema and crashes with a fatal GLib-GIO-ERROR. Use a local schema copy
# that restores those keys. Only applied if the system schema is missing
# the key (checked via gsettings, which reports an error for missing keys).
if ! gsettings list-keys org.gnome.settings-daemon.plugins.xsettings 2>/dev/null | grep -qx 'antialiasing'; then
    OVERRIDE_DIR="$SCRIPT_DIR/gsettings-override"
    if [ ! -f "$OVERRIDE_DIR/gschemas.compiled" ]; then
        glib-compile-schemas "$OVERRIDE_DIR" 2>/dev/null || true
    fi
    if [ -f "$OVERRIDE_DIR/gschemas.compiled" ]; then
        export GSETTINGS_SCHEMA_DIR="$OVERRIDE_DIR${GSETTINGS_SCHEMA_DIR:+:$GSETTINGS_SCHEMA_DIR}:/usr/share/glib-2.0/schemas"
    fi
fi

exec "$PYTHON" gui.py "$@"
