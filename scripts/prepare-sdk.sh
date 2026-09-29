#!/usr/bin/env bash
# Prepare a fresh STM32-Sidewalk-SDK download for the MEMS demo build.
#
# Thin wrapper kept so existing commands and documentation keep working.
# The implementation is scripts/prepare-sdk.py, which needs only Python and
# runs the same from PowerShell, Command Prompt, macOS, and Linux:
#
#     python scripts/prepare-sdk.py
#
# Arguments and environment variables are passed through unchanged.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for py in python3 python py; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
        exec "$py" "$here/prepare-sdk.py" "$@"
    fi
done
echo "error: Python 3.8 or newer was not found on PATH." >&2
echo "Install it from https://www.python.org/downloads/ and run:" >&2
echo "    python scripts/prepare-sdk.py" >&2
exit 1
