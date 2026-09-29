#!/usr/bin/env bash
# Erase the board, then flash the firmware and the manufacturing image.
#
# Thin wrapper kept so existing commands and documentation keep working.
# The implementation is tools/flash_wba.py, which needs only Python and
# runs the same from PowerShell, Command Prompt, macOS, and Linux:
#
#     python tools/flash_wba.py <firmware.hex> <mfg.hex>
#
# Arguments and environment variables are passed through unchanged.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for py in python3 python py; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
        exec "$py" "$here/flash_wba.py" "$@"
    fi
done
echo "error: Python 3.8 or newer was not found on PATH." >&2
echo "Install it from https://www.python.org/downloads/ and run:" >&2
echo "    python tools/flash_wba.py <firmware.hex> <mfg.hex>" >&2
exit 1
