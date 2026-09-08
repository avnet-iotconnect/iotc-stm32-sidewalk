#!/usr/bin/env bash
# Flash a Nucleo-WBA55CG or Nucleo-WBA65RI board with a sid_ble firmware hex + a
# per-device Sidewalk manufacturing hex, using STM32_Programmer_CLI under
# connect-under-reset (mode=UR) with a one-shot retry on the intermittent
# DEV_CONNECT_ERR that the WBA throws when prior firmware is in deep-sleep.
#
# Board-agnostic: both hex files carry their own flash addresses, so the same
# script flashes either board. Just pass the matching firmware/mfg hex — for
# WBA65 that is the sid_ble_wba65 build and a WBA65xI-provisioned mfg.hex.
#
# Usage:
#   flash_wba55.sh <firmware.hex> <mfg.hex>
#
# Examples:
#   # WBA55
#   flash_wba55.sh \
#     STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_ble_wba55.hex \
#     /tmp/sidewalk-mfg/STtempIKS4A1/mfg_STtempIKS4A1.hex
#   # WBA65
#   flash_wba55.sh \
#     STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA65/Debug_Nucleo-WBA65/sid_ble_wba65.hex \
#     /tmp/sidewalk-mfg/STtempIKS4A1/mfg_STtempIKS4A1.hex
#
# Each call does a chip-erase first so leftover LittleFS regions can't conflict.
set -u
fw=${1:-}
mfg=${2:-}
if [[ -z "$fw" || -z "$mfg" ]]; then
    echo "usage: $0 <firmware.hex> <mfg.hex>" >&2
    exit 2
fi
for f in "$fw" "$mfg"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: file not found: $f" >&2
        exit 2
    fi
done

# Locate STM32_Programmer_CLI. STM32CubeProgrammer does not add itself to PATH
# on Windows, so fall back to the default install locations before giving up.
find_programmer() {
    if [[ -n "${STM32_PROGRAMMER_CLI:-}" ]]; then
        echo "$STM32_PROGRAMMER_CLI"
        return 0
    fi
    if command -v STM32_Programmer_CLI >/dev/null 2>&1; then
        echo "STM32_Programmer_CLI"
        return 0
    fi
    local candidates=(
        "/c/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe"
        "/c/Program Files (x86)/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe"
        "/Applications/STMicroelectronics/STM32Cube/STM32CubeProgrammer/STM32CubeProgrammer.app/Contents/MacOs/bin/STM32_Programmer_CLI"
        "$HOME/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI"
        "/opt/stm32cubeprog/bin/STM32_Programmer_CLI"
    )
    for c in "${candidates[@]}"; do
        [[ -x "$c" ]] && { echo "$c"; return 0; }
    done
    {
        echo "ERROR: STM32_Programmer_CLI not found."
        echo
        echo "It ships with STM32CubeProgrammer, which does not add itself to PATH."
        echo "Either add its bin directory to PATH, e.g. in Git Bash:"
        echo "    export PATH=\"\$PATH:/c/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin\""
        echo "or point STM32_PROGRAMMER_CLI at the executable:"
        echo "    STM32_PROGRAMMER_CLI=/path/to/STM32_Programmer_CLI $0 ..."
        echo
        echo "Install it from https://www.st.com/en/development-tools/stm32cubeprog.html"
    } >&2
    return 1
}

PROG="$(find_programmer)" || exit 2
COMMON_ARGS=(-c port=SWD mode=UR)

# Helper: run the programmer with one retry on DEV_CONNECT_ERR / connect failures.
run_step() {
    local label=$1; shift
    local attempt
    for attempt in 1 2; do
        echo
        echo "[$label] attempt $attempt: $PROG ${COMMON_ARGS[*]} $*"
        if "$PROG" "${COMMON_ARGS[@]}" "$@"; then
            return 0
        fi
        echo "[$label] attempt $attempt failed; retrying..." >&2
        sleep 1
    done
    echo "[$label] FAILED after retries." >&2
    return 1
}

echo "Programmer : $PROG"
echo "Firmware   : $fw"
echo "MFG image  : $mfg"

run_step "erase"     -e all || exit 1
run_step "firmware"  -w "$fw" || exit 1
run_step "mfg"       -w "$mfg" || exit 1

echo
echo "Done. Power-cycle / reset the board to start the firmware."
