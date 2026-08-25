#!/usr/bin/env bash
# Build the <board> + IKS4A1 and <board> + IKS5A1 firmware variants headlessly,
# then copy the resulting .hex files into iotc-stm32-sidewalk/binaries/.
#
# The target Nucleo board is selected with the BOARD env var (default wba55):
#   BOARD=wba55  -> STM32CubeIDE/STM32WBA55, config Debug_Nucleo-WBA55, sid_ble_wba55
#   BOARD=wba65  -> STM32CubeIDE/STM32WBA65, config Debug_Nucleo-WBA65, sid_ble_wba65
#
# Usage:
#   ./scripts/build-firmware.sh                 # WBA55, build both shields
#   ./scripts/build-firmware.sh iks4a1          # WBA55, IKS4A1 only
#   BOARD=wba65 ./scripts/build-firmware.sh     # WBA65, build both shields
#
# LOCATION=1 composes the BLE L1 location overlay onto any variant
# (examples/sidewalk-mems-location-wba55): swaps the Sidewalk archive
# basic->full, enables SID_SDK_CONFIG_ENABLE_LOCATION=1 +
# SID_APP_LOCATION_ENABLED=1, and suffixes the output hex with `_loc`.
# Requires the location overlay applied to the SDK once (location_wba55.c/.h
# in STM32_WPAN/App + the guarded app_sidewalk.c hooks — see
# examples/sidewalk-location-wba55/firmware/README.md).
#   LOCATION=1 ./scripts/build-firmware.sh iks5a1
#   BOARD=wba65 LOCATION=1 ./scripts/build-firmware.sh iks4a1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_ROOT="${SDK_ROOT:-$HOME/dev/sidewalk/STM32-Sidewalk-SDK}"

# Board-specific CubeIDE project dir / build config / project (= hex) name.
BOARD="${BOARD:-wba55}"
case "$BOARD" in
    wba55|WBA55) PROJ_SUB="STM32WBA55"; BUILD_CFG="Debug_Nucleo-WBA55"; PROJ_NAME="sid_ble_wba55" ;;
    wba65|WBA65) PROJ_SUB="STM32WBA65"; BUILD_CFG="Debug_Nucleo-WBA65"; PROJ_NAME="sid_ble_wba65" ;;
    *) echo "unknown BOARD: $BOARD (expected: wba55 | wba65)" >&2; exit 1 ;;
esac

PROJ_DIR="$SDK_ROOT/apps/st/stm32wba/sid_ble/STM32CubeIDE/$PROJ_SUB"
CUBE_IDE="${CUBE_IDE:-/opt/st/stm32cubeide_1.18.0/headless-build.sh}"
OUT_DIR="$REPO_ROOT/binaries"
CPROJECT="$PROJ_DIR/.cproject"
TARGET="${1:-both}"

[[ -x "$CUBE_IDE" ]] || { echo "STM32CubeIDE headless build not found at $CUBE_IDE" >&2; exit 1; }
[[ -d "$PROJ_DIR" ]] || { echo "SDK project dir not found at $PROJ_DIR" >&2; exit 1; }

LOCATION="${LOCATION:-0}"
if [[ "$LOCATION" == "1" ]]; then
    APP_DIR="$SDK_ROOT/apps/st/stm32wba/sid_ble/STM32_WPAN/App"
    [[ -f "$APP_DIR/location_wba55.c" ]] || {
        echo "LOCATION=1 but $APP_DIR/location_wba55.c is missing." >&2
        echo "Apply the location overlay first: examples/sidewalk-location-wba55/firmware/README.md" >&2
        exit 1
    }
    grep -q "location_wba55_init" "$APP_DIR/app_sidewalk.c" || {
        echo "LOCATION=1 but app_sidewalk.c has no location hooks." >&2
        echo "Apply the guarded hooks: examples/sidewalk-location-wba55/firmware/README.md" >&2
        exit 1
    }
fi

mkdir -p "$OUT_DIR"

backup="$(mktemp)"
cp "$CPROJECT" "$backup"
restore() { cp "$backup" "$CPROJECT"; rm -f "$backup"; }
trap restore EXIT

build_one() {
    local variant="$1"    # iks4a1 | iks5a1
    local ws hex suffix
    suffix="$variant"
    [[ "$LOCATION" == "1" ]] && suffix="${variant}_loc"
    ws="/tmp/${BOARD}_ws_${suffix}"
    hex="$PROJ_DIR/$BUILD_CFG/$PROJ_NAME.hex"

    cp "$backup" "$CPROJECT"  # start from a clean cproject each variant
    if [[ "$variant" == "iks5a1" ]]; then
        sed -i \
            -e 's|SID_APP_IKS4A1_ENABLED=1|SID_APP_IKS4A1_ENABLED=0|g' \
            -e 's|SID_APP_IKS5A1_ENABLED=0|SID_APP_IKS5A1_ENABLED=1|g' \
            "$CPROJECT"
    fi
    if [[ "$LOCATION" == "1" ]]; then
        # Location overlay: full (location-enabled) archive + feature defines.
        # The IKS5A1 define is =0 or =1 depending on the variant — match both.
        sed -i \
            -e 's|sidewalk_sdk_basic|sidewalk_sdk_full|g' \
            -e 's|\(\s*\)\(<listOptionValue builtIn="false" value="SID_APP_IKS5A1_ENABLED=[01]"/>\)|\1\2\n\1<listOptionValue builtIn="false" value="SID_SDK_CONFIG_ENABLE_LOCATION=1"/>\n\1<listOptionValue builtIn="false" value="SID_APP_LOCATION_ENABLED=1"/>|g' \
            "$CPROJECT"
    fi

    echo "== building $BOARD $suffix =="
    "$CUBE_IDE" \
        -data "$ws" \
        -import "$PROJ_DIR" \
        -cleanBuild "$PROJ_NAME/$BUILD_CFG" \
        -no-indexer | tail -3

    cp "$hex" "$OUT_DIR/${PROJ_NAME}_${suffix}.hex"
    echo "wrote $OUT_DIR/${PROJ_NAME}_${suffix}.hex"
}

case "$TARGET" in
    iks4a1) build_one iks4a1 ;;
    iks5a1) build_one iks5a1 ;;
    both)   build_one iks4a1; build_one iks5a1 ;;
    *)      echo "unknown target: $TARGET (expected: iks4a1 | iks5a1 | both)" >&2; exit 1 ;;
esac

ls -la "$OUT_DIR"/*.hex
