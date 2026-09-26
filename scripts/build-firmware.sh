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
#   ./scripts/build-firmware.sh location        # WBA55, location-only (no MEMS shield;
#                                               #   stock counter uplink + BLE L1 resolves,
#                                               #   examples/sidewalk-location-wba55) ->
#                                               #   binaries/sid_ble_<board>_location.hex
#
# LPM_STANDBY=0 builds with Stop-mode-only low power (CFG_LPM_STDBY_SUPPORTED=0
# in Config/app_conf.h, restored after the build). Use it when a board shows
# unexplained restarts while idle: Standby wake-up goes through the reset
# vector and, if the resume is rejected, looks exactly like a cold reboot.
#   LPM_STANDBY=0 ./scripts/build-firmware.sh location
#
# DEMO_PERIOD_S=<n> sets the stock counter demo's uplink period (default 120 s,
# DEMO_MESSAGE_DELAY_MS in app_sidewalk.c; restored after the build). At 60 s
# or less the BLE link never idles, so the device stays connected and never
# enters Standby. Output suffix _p<n>.
#   DEMO_PERIOD_S=15 ./scripts/build-firmware.sh location
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
OUT_DIR="$REPO_ROOT/binaries"
CPROJECT="$PROJ_DIR/.cproject"
TARGET="${1:-both}"

# Locate STM32CubeIDE's headless builder. CUBE_IDE wins; otherwise search the
# default install locations, newest version first, on Windows/Linux/macOS.
CUBE_IDE_WIN=0
find_cube_ide() {
    local c candidates=()
    if [[ -n "${CUBE_IDE:-}" ]]; then
        candidates=("$CUBE_IDE")
    else
        while IFS= read -r c; do candidates+=("$c"); done < <(
            ls -d /c/ST/STM32CubeIDE_*/STM32CubeIDE/headless-build.bat \
                  "/c/Program Files/STMicroelectronics/STM32CubeIDE"*/STM32CubeIDE/headless-build.bat \
                  /opt/st/stm32cubeide_*/headless-build.sh \
                  "$HOME/st/stm32cubeide_"*/headless-build.sh \
                  /Applications/STM32CubeIDE.app/Contents/MacOs/headless-build.sh \
                  2>/dev/null | sort -r)
    fi
    for c in "${candidates[@]}"; do
        [[ -f "$c" ]] || continue
        CUBE_IDE="$c"
        [[ "$c" == *.bat ]] && CUBE_IDE_WIN=1
        return 0
    done
    {
        echo "error: STM32CubeIDE headless build not found."
        echo
        echo "Building the firmware requires STM32CubeIDE to be installed (you do"
        echo "not have to open it -- this drives its headless builder)."
        echo "    https://www.st.com/en/development-tools/stm32cubeide.html"
        echo
        echo "If it is installed somewhere unusual, point CUBE_IDE at the launcher:"
        echo "    CUBE_IDE=/c/ST/STM32CubeIDE_1.18.0/STM32CubeIDE/headless-build.bat $0"
    } >&2
    return 1
}

find_cube_ide || exit 1
echo "CubeIDE    : $CUBE_IDE"

# The Windows builder is a native binary and cannot read MSYS paths
# (/c/Users/...), so hand it Windows paths instead.
ide_path() {
    if [[ "$CUBE_IDE_WIN" == 1 ]]; then cygpath -w "$1"; else echo "$1"; fi
}
[[ -d "$PROJ_DIR" ]] || { echo "SDK project dir not found at $PROJ_DIR" >&2; exit 1; }

LOCATION="${LOCATION:-0}"
# The location-only target always needs the location overlay.
[[ "$TARGET" == "location" ]] && LOCATION=1
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
APP_CONF="$SDK_ROOT/apps/st/stm32wba/sid_ble/Config/app_conf.h"
conf_backup="$(mktemp)"
cp "$APP_CONF" "$conf_backup"
restore() { cp "$backup" "$CPROJECT"; rm -f "$backup"; cp "$conf_backup" "$APP_CONF"; rm -f "$conf_backup"; }
trap restore EXIT

APP_SIDEWALK="$SDK_ROOT/apps/st/stm32wba/sid_ble/STM32_WPAN/App/app_sidewalk.c"
sidewalk_backup="$(mktemp)"
cp "$APP_SIDEWALK" "$sidewalk_backup"
restore_all() { restore; cp "$sidewalk_backup" "$APP_SIDEWALK"; rm -f "$sidewalk_backup"; }
trap restore_all EXIT

DEMO_PERIOD_S="${DEMO_PERIOD_S:-}"
if [[ -n "$DEMO_PERIOD_S" ]]; then
    sed -i -e "s|^#define DEMO_MESSAGE_DELAY_MS        (2u \* 60000u)|#define DEMO_MESSAGE_DELAY_MS        (${DEMO_PERIOD_S}u * 1000u)|" "$APP_SIDEWALK"
    grep -q "DEMO_MESSAGE_DELAY_MS        (${DEMO_PERIOD_S}u \* 1000u)" "$APP_SIDEWALK" || { echo "failed to set DEMO_MESSAGE_DELAY_MS in $APP_SIDEWALK" >&2; exit 1; }
    echo "Demo period: ${DEMO_PERIOD_S} s (DEMO_MESSAGE_DELAY_MS)"
fi

LPM_STANDBY="${LPM_STANDBY:-1}"
if [[ "$LPM_STANDBY" == "0" ]]; then
    # Stop-mode-only low power: no Standby entry, so no reset-vector wake-ups.
    sed -i -e 's|^#define CFG_LPM_STDBY_SUPPORTED  (1)|#define CFG_LPM_STDBY_SUPPORTED  (0)|' "$APP_CONF"
    grep -q "CFG_LPM_STDBY_SUPPORTED  (0)" "$APP_CONF" || { echo "failed to set CFG_LPM_STDBY_SUPPORTED=0 in $APP_CONF" >&2; exit 1; }
    echo "LPM        : Stop-only (CFG_LPM_STDBY_SUPPORTED=0)"
fi

build_one() {
    local variant="$1"    # iks4a1 | iks5a1 | location
    local ws hex suffix
    suffix="$variant"
    [[ "$variant" != "location" && "$LOCATION" == "1" ]] && suffix="${variant}_loc"
    [[ "$LPM_STANDBY" == "0" ]] && suffix="${suffix}_stop"
    [[ -n "$DEMO_PERIOD_S" ]] && suffix="${suffix}_p${DEMO_PERIOD_S}"
    ws="/tmp/${BOARD}_ws_${suffix}"
    hex="$PROJ_DIR/$BUILD_CFG/$PROJ_NAME.hex"

    cp "$backup" "$CPROJECT"  # start from a clean cproject each variant
    if [[ "$variant" == "iks5a1" ]]; then
        sed -i \
            -e 's|SID_APP_IKS4A1_ENABLED=1|SID_APP_IKS4A1_ENABLED=0|g' \
            -e 's|SID_APP_IKS5A1_ENABLED=0|SID_APP_IKS5A1_ENABLED=1|g' \
            "$CPROJECT"
    elif [[ "$variant" == "location" ]]; then
        # No MEMS shield: both sensor flags off -> app_sidewalk.c falls back to
        # the stock counter payload; the guarded location hooks still compile.
        sed -i \
            -e 's|SID_APP_IKS4A1_ENABLED=1|SID_APP_IKS4A1_ENABLED=0|g' \
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
    # A workspace left over from a build against a different SDK path makes
    # the import fail (same project name, different location), so start clean.
    rm -rf "$ws"
    local log="$OUT_DIR/build_${PROJ_NAME}_${suffix}.log"
    if "$CUBE_IDE" \
        -data "$(ide_path "$ws")" \
        -import "$(ide_path "$PROJ_DIR")" \
        -cleanBuild "$PROJ_NAME/$BUILD_CFG" \
        -no-indexer > "$log" 2>&1 && grep -q "Build Finished" "$log" && [[ -f "$hex" ]]
    then
        grep "Build Finished" "$log" | tail -1
    else
        echo "build FAILED -- compiler errors:" >&2
        grep -E "error:|undefined reference|multiple definition|No such file|\*\*\* \[" "$log" >&2 || tail -20 "$log" >&2
        echo "full log: $log" >&2
        return 1
    fi

    cp "$hex" "$OUT_DIR/${PROJ_NAME}_${suffix}.hex"
    echo "wrote $OUT_DIR/${PROJ_NAME}_${suffix}.hex"
}

case "$TARGET" in
    iks4a1) build_one iks4a1 ;;
    iks5a1) build_one iks5a1 ;;
    location) build_one location ;;
    both)   build_one iks4a1; build_one iks5a1 ;;
    *)      echo "unknown target: $TARGET (expected: iks4a1 | iks5a1 | location | both)" >&2; exit 1 ;;
esac

ls -la "$OUT_DIR"/*.hex
