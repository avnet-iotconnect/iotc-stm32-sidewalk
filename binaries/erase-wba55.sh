#!/usr/bin/env bash
# erase-wba55.sh — mass-erase the STM32WBA55 even when the current firmware
# slams it into low-power (Standby/Shutdown) right after boot.
#
# Connects UNDER RESET (NRST held low while attaching), skips the failing AP0
# (ap=1), drops the SWD clock (freq=1800) for a robust low-power attach, and
# RETRIES until the erase catches the target. After erase the flash is blank,
# so the MCU has nothing to run and can no longer sleep.
#
# Usage:  ./erase-wba55.sh
set -euo pipefail

CONN="port=SWD mode=UR ap=1 freq=1800"       # Under Reset, AP1, slow clock
MAX_TRIES=25

echo "== Mass-erase under reset (retrying to catch the low-power target) =="
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
