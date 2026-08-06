#!/usr/bin/env bash
# Roll back the three post-first-success enhancements as a group:
#   E) app version bump 1.1.0 -> 1.1.1  (stm32_sidewalk_sdk_version.def)
#   F) ota_status reported via AIM verification state instead of the broken KV flag
#   G) app_version (SID_APP_PROJECT_*) appended to the capability uplink (tag 0x14)
# Leaves the SBDT-registration fix, flash space fixes, CRC fix, and OTA logging in place.
#
# Usage:  ./rollback-enhancements.sh            # revert E+F+G
#         ./rollback-enhancements.sh --reapply   # re-apply them
#
# Rebuild + reflash the app afterwards for the change to take effect.
set -euo pipefail
SDK="/home/mlamp/dev/sidewalk/STM32-Sidewalk-SDK"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH="$HERE/ota_status_appversion_versionbump.patch"
cd "$SDK"
if [[ "${1:-}" == "--reapply" ]]; then
    git apply "$PATCH"
    echo "Enhancements RE-APPLIED (version 1.1.1, ota_status fix, app_version). Rebuild + reflash."
else
    git apply -R "$PATCH"
    echo "Enhancements ROLLED BACK (version 1.1.0, KV-based ota_status, no app_version). Rebuild + reflash."
fi
