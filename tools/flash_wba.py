#!/usr/bin/env python3
"""Flash a NUCLEO-WBA55CG or NUCLEO-WBA65RI with the firmware and its manufacturing image.

Erases the chip, writes the firmware hex, then writes the per-device Sidewalk
manufacturing hex. Every step connects under reset (mode=UR) and is retried
once, because the WBA intermittently answers DEV_CONNECT_ERR when the firmware
already on it is in deep sleep.

Board-agnostic: both hex files carry their own flash addresses, so the same
command flashes either board. Pass the firmware built for your board and the
mfg.hex provisioned for it.

Runs the same on Windows (PowerShell / Command Prompt), macOS, and Linux.

Usage:
    python tools/flash_wba.py <firmware.hex> <mfg.hex>
    python tools/flash_wba.py --list-probes        # check the board's ST-LINK is visible

Example:
    python tools/flash_wba.py binaries/sid_ble_wba55_iks4a1.hex binaries/sidewalk-mfg/wba-mems-01/mfg.hex

STM32_Programmer_CLI ships with STM32CubeProgrammer, which does not add itself
to PATH. This script finds it in the default install locations; if yours is
elsewhere, pass --programmer or set STM32_PROGRAMMER_CLI.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONNECT = ["-c", "port=SWD", "mode=UR"]


def find_programmer(override: str | None) -> str:
    if override:
        return override
    on_path = shutil.which("STM32_Programmer_CLI")
    if on_path:
        return on_path
    home = Path.home()
    candidates = [
        Path("C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe"),
        Path("C:/Program Files (x86)/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe"),
        Path("/Applications/STMicroelectronics/STM32Cube/STM32CubeProgrammer/STM32CubeProgrammer.app/Contents/MacOs/bin/STM32_Programmer_CLI"),
        home / "STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI",
        Path("/opt/stm32cubeprog/bin/STM32_Programmer_CLI"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    sys.exit(
        "ERROR: STM32_Programmer_CLI not found.\n"
        "\n"
        "It ships with STM32CubeProgrammer:\n"
        "    https://www.st.com/en/development-tools/stm32cubeprog.html\n"
        "\n"
        "If it is installed somewhere unusual, point at the executable:\n"
        "    python tools/flash_wba.py --programmer <path to STM32_Programmer_CLI> <firmware.hex> <mfg.hex>"
    )


def run_step(programmer: str, label: str, arguments: list[str]) -> bool:
    """Run one programmer command, retrying once on a connect failure."""
    command = [programmer, *CONNECT, *arguments]
    for attempt in (1, 2):
        print()
        print(f"[{label}] attempt {attempt}: {' '.join(command)}", flush=True)
        if subprocess.run(command).returncode == 0:
            return True
        print(f"[{label}] attempt {attempt} failed; retrying...", file=sys.stderr)
        time.sleep(1)
    print(f"[{label}] FAILED after retries.", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Erase the board, then flash the firmware and the manufacturing image.")
    parser.add_argument("firmware", nargs="?", help="firmware hex, e.g. binaries/sid_ble_wba55_iks4a1.hex")
    parser.add_argument("mfg", nargs="?", help="manufacturing hex, e.g. binaries/sidewalk-mfg/<device>/mfg.hex")
    parser.add_argument("--list-probes", action="store_true",
                        help="list the ST-LINK probes the programmer can see, then exit")
    parser.add_argument("--programmer", default=os.environ.get("STM32_PROGRAMMER_CLI"),
                        help="path to STM32_Programmer_CLI (default: auto-detected)")
    args = parser.parse_args()

    if args.list_probes:
        return subprocess.run([find_programmer(args.programmer), "-l"]).returncode
    if not args.firmware or not args.mfg:
        parser.error("the following arguments are required: firmware, mfg")

    for name in (args.firmware, args.mfg):
        if not Path(name).is_file():
            print(f"ERROR: file not found: {name}", file=sys.stderr)
            return 2

    programmer = find_programmer(args.programmer)
    print(f"Programmer : {programmer}")
    print(f"Firmware   : {args.firmware}")
    print(f"MFG image  : {args.mfg}")

    # Chip erase first so leftover LittleFS regions cannot conflict.
    steps = (("erase", ["-e", "all"]), ("firmware", ["-w", args.firmware]), ("mfg", ["-w", args.mfg]))
    for label, arguments in steps:
        if not run_step(programmer, label, arguments):
            return 1

    print()
    print("Done. Press the black RESET button, or power-cycle the board, to start the firmware.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
