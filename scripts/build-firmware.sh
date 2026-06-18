#!/usr/bin/env bash
# Build the WBA55 + IKS4A1 and WBA55 + IKS5A1 firmware variants headlessly,
# then copy the resulting .hex files into iotc-stm32-sidewalk/binaries/.
#
# Usage:
#   ./scripts/build-firmware.sh                 # build both
#   ./scripts/build-firmware.sh iks4a1          # IKS4A1 only
#   ./scripts/build-firmware.sh iks5a1          # IKS5A1 only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_ROOT="${SDK_ROOT:-$HOME/dev/sidewalk/STM32-Sidewalk-SDK}"
PROJ_DIR="$SDK_ROOT/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55"
CUBE_IDE="${CUBE_IDE:-/opt/st/stm32cubeide_1.18.0/headless-build.sh}"
OUT_DIR="$REPO_ROOT/binaries"
CPROJECT="$PROJ_DIR/.cproject"
TARGET="${1:-both}"

[[ -x "$CUBE_IDE" ]] || { echo "STM32CubeIDE headless build not found at $CUBE_IDE" >&2; exit 1; }
[[ -d "$PROJ_DIR" ]] || { echo "SDK project dir not found at $PROJ_DIR" >&2; exit 1; }

mkdir -p "$OUT_DIR"

backup="$(mktemp)"
cp "$CPROJECT" "$backup"
restore() { cp "$backup" "$CPROJECT"; rm -f "$backup"; }
trap restore EXIT

build_one() {
    local variant="$1"    # iks4a1 | iks5a1
    local ws hex
    ws="/tmp/wba55_ws_${variant}"
    hex="$PROJ_DIR/Debug_Nucleo-WBA55/sid_ble_wba55.hex"

    cp "$backup" "$CPROJECT"  # start from a clean cproject each variant
    if [[ "$variant" == "iks5a1" ]]; then
        sed -i \
            -e 's|SID_APP_IKS4A1_ENABLED=1|SID_APP_IKS4A1_ENABLED=0|g' \
            -e 's|SID_APP_IKS5A1_ENABLED=0|SID_APP_IKS5A1_ENABLED=1|g' \
            "$CPROJECT"
    fi

    echo "== building $variant =="
    "$CUBE_IDE" \
        -data "$ws" \
        -import "$PROJ_DIR" \
        -cleanBuild "sid_ble_wba55/Debug_Nucleo-WBA55" \
        -no-indexer | tail -3

    cp "$hex" "$OUT_DIR/sid_ble_wba55_${variant}.hex"
    echo "wrote $OUT_DIR/sid_ble_wba55_${variant}.hex"
}

case "$TARGET" in
    iks4a1) build_one iks4a1 ;;
    iks5a1) build_one iks5a1 ;;
    both)   build_one iks4a1; build_one iks5a1 ;;
    *)      echo "unknown target: $TARGET (expected: iks4a1 | iks5a1 | both)" >&2; exit 1 ;;
esac

ls -la "$OUT_DIR"/*.hex
