#!/usr/bin/env bash
# flash-wba55.sh — reliably program the STM32WBA55 even when the current
# firmware slams it into low-power (Standby/Shutdown) right after boot.
#
# The trick is NOT power cycling (the ST-LINK shares USB power with the target).
# It is: connect UNDER RESET so NRST is held low while attaching, skip the
# failing AP0 (ap=1), drop the SWD clock (freq=1800) for a robust low-power
# attach, and RETRY the mass-erase until it catches the target. Once flash is
# erased the MCU has nothing to run, so it can no longer sleep and the
# subsequent programming steps connect normally.
#
# Usage:
#   ./flash-wba55.sh                         # uses sid_ble_wba55_location_v2.hex
#   ./flash-wba55.sh sid_ble_wba55_iks5a1.hex
set -euo pipefail
cd "$(dirname "$0")"

CONN="port=SWD mode=UR ap=1 freq=1800"       # Under Reset, AP1, slow clock
APP="${1:-sid_ble_wba55_location_v2.hex}"
MFG="sidewalk-mfg/shared18-StSidewalk5/mfg.bin"
MFG_ADDR="0x080FE000"
MAX_TRIES=25

[ -f "$APP" ] || { echo "App file not found: $APP" >&2; exit 1; }
[ -f "$MFG" ] || { echo "MFG file not found: $MFG" >&2; exit 1; }

echo "== Step 1/3: mass-erase under reset (retrying to catch the low-power target) =="
n=0
until STM32_Programmer_CLI -c $CONN -e all; do
    n=$((n + 1))
    if [ "$n" -ge "$MAX_TRIES" ]; then
        echo ""
        echo "Still can't attach after $n tries. The firmware is sleeping faster than"
        echo "under-reset can catch it. Fall back to the ROM bootloader:"
        echo "  1) Hold BOOT0 high (or tap+hold physical RESET while this loop runs)."
        echo "  2) Re-run this script."
        exit 1
    fi
    echo "  attach failed (try $n/$MAX_TRIES) — retrying under reset..."
    sleep 0.4
done
echo "== Erase OK — flash is blank, target can no longer sleep. =="

echo "== Step 2/3: program application: $APP =="
STM32_Programmer_CLI -c $CONN -d "$APP" -v

echo "== Step 3/3: program mfg data at $MFG_ADDR =="
STM32_Programmer_CLI -c $CONN -d "$MFG" "$MFG_ADDR" -v -rst

echo "== DONE =="
