#!/usr/bin/env bash
# Roll back ONLY the space/flash-related OTA fixes (AIM erase-alignment fix + CRC
# RAM-fallback fix), returning the SDK to the pre-fix behavior for those two items.
# Leaves the OTA debug logging and the SBDT-registration fix in place.
#
# Usage:  ./rollback-space-fixes.sh          # revert the two space fixes
#         ./rollback-space-fixes.sh --reapply # re-apply them again
#
# After running, rebuild + reflash the app for the change to take effect:
#   see dev-notes/OTA_DEBUG_LOGGING.md "Rebuild" section.
set -euo pipefail

SDK="/home/mlamp/dev/sidewalk/STM32-Sidewalk-SDK"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERASE_PATCH="$HERE/aim_erase_align_fix.patch"
CRC_PATCH="$HERE/crc_ram_fallback_fix.patch"

cd "$SDK"

if [[ "${1:-}" == "--reapply" ]]; then
    echo "Re-applying space fixes..."
    git apply "$ERASE_PATCH"
    git apply "$CRC_PATCH"
    echo "Space fixes RE-APPLIED. Rebuild + reflash the app."
else
    echo "Rolling back space fixes (erase-alignment + CRC RAM-fallback)..."
    git apply -R "$ERASE_PATCH"
    git apply -R "$CRC_PATCH"
    echo "Space fixes ROLLED BACK. Rebuild + reflash the app to return to pre-fix behavior."
fi
