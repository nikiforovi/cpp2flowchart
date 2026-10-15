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
exec "$PYTHON" gui.py "$@"
