#!/usr/bin/env python3
"""Build the sid_ble firmware headlessly and copy the .hex into binaries/.

Runs the same on Windows (PowerShell / Command Prompt), macOS, and Linux. It
drives STM32CubeIDE's headless builder, so STM32CubeIDE must be installed, but
you never open it. It needs only Python: no Git and no Git Bash.

Usage:
    python scripts/build-firmware.py                      # NUCLEO-WBA55CG, both MEMS shields
    python scripts/build-firmware.py --board wba65        # NUCLEO-WBA65RI, both MEMS shields
    python scripts/build-firmware.py iks4a1               # one shield only
    python scripts/build-firmware.py location             # location-only, no MEMS shield

Targets:
    both      IKS4A1 and IKS5A1 (default)
    iks4a1    X-NUCLEO-IKS4A1 only
    iks5a1    X-NUCLEO-IKS5A1 only
    location  stock counter uplink + BLE L1 location resolves
              (examples/sidewalk-location-wba55) -> sid_ble_<board>_location.hex

Options (each also reads the environment variable of the same name):
    --board wba55|wba65   BOARD          host board (default wba55)
    --location            LOCATION=1     compose the BLE L1 location overlay onto a
                                         MEMS variant (examples/sidewalk-mems-location-wba55):
                                         swaps the Sidewalk archive basic->full and enables
                                         the location defines. Output suffix _loc. Needs the
                                         location overlay applied to the SDK once, see
                                         examples/sidewalk-location-wba55/firmware/README.md
    --stop-only           LPM_STANDBY=0  Stop-mode-only low power. Use it when a board shows
                                         unexplained restarts while idle: Standby wake-up goes
                                         through the reset vector and, if the resume is
                                         rejected, looks exactly like a cold reboot. Suffix _stop.
    --demo-period N       DEMO_PERIOD_S  uplink period of the stock counter demo in seconds
                                         (default 120). At 60 s or less the BLE link never
                                         idles, so the device stays connected. Suffix _p<N>.
    --cube-ide PATH       CUBE_IDE       STM32CubeIDE headless-build launcher
    --sdk-root PATH       SDK_ROOT       STM32-Sidewalk-SDK folder

The project files this script edits for a build are restored afterwards.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sidewalk_common as common  # noqa: E402

REPO_ROOT = common.REPO_ROOT
OUT_DIR = REPO_ROOT / "binaries"

BOARDS = {
    "wba55": ("STM32WBA55", "Debug_Nucleo-WBA55", "sid_ble_wba55"),
    "wba65": ("STM32WBA65", "Debug_Nucleo-WBA65", "sid_ble_wba65"),
}
TARGETS = {"both": ("iks4a1", "iks5a1"), "iks4a1": ("iks4a1",), "iks5a1": ("iks5a1",), "location": ("location",)}
ERROR_LINE = re.compile(r"error:|undefined reference|multiple definition|No such file|\*\*\* \[")


def version_key(path: str) -> list:
    """Sort key that orders 1.9.0 before 1.18.0."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path)]


def find_cube_ide(override: str | None) -> Path:
    """Locate STM32CubeIDE's headless builder, newest version first."""
    if override:
        candidates = [override]
    else:
        home = str(Path.home())
        patterns = [
            "C:/ST/STM32CubeIDE_*/STM32CubeIDE/headless-build.bat",
            "C:/Program Files/STMicroelectronics/STM32CubeIDE*/STM32CubeIDE/headless-build.bat",
            "/opt/st/stm32cubeide_*/headless-build.sh",
            home + "/st/stm32cubeide_*/headless-build.sh",
            "/Applications/STM32CubeIDE.app/Contents/MacOs/headless-build.sh",
        ]
        candidates = []
        for pattern in patterns:
            candidates.extend(glob.glob(pattern))
        candidates.sort(key=version_key, reverse=True)
    for candidate in candidates:
        if Path(candidate).is_file():
            return Path(candidate)
    sys.exit(
        "error: STM32CubeIDE headless build not found.\n"
        "\n"
        "Building the firmware requires STM32CubeIDE to be installed (you do\n"
        "not have to open it -- this drives its headless builder).\n"
        "    https://www.st.com/en/development-tools/stm32cubeide.html\n"
        "\n"
        "If it is installed somewhere unusual, point --cube-ide at the launcher:\n"
        "    python scripts/build-firmware.py --cube-ide C:/ST/STM32CubeIDE_1.18.0/STM32CubeIDE/headless-build.bat"
    )


def substitute(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_bytes().decode("utf-8", errors="surrogateescape")
    if old not in text:
        sys.exit(f"failed to set {what} in {path}")
    path.write_bytes(text.replace(old, new).encode("utf-8", errors="surrogateescape"))


def configure_cproject(original: bytes, variant: str, location: bool) -> bytes:
    """Return the .cproject content for one variant, starting from the pristine copy."""
    text = original.decode("utf-8", errors="surrogateescape")
    if variant == "iks5a1":
        text = text.replace("SID_APP_IKS4A1_ENABLED=1", "SID_APP_IKS4A1_ENABLED=0")
        text = text.replace("SID_APP_IKS5A1_ENABLED=0", "SID_APP_IKS5A1_ENABLED=1")
    elif variant == "location":
        # No MEMS shield: both sensor flags off -> app_sidewalk.c falls back to
        # the stock counter payload; the guarded location hooks still compile.
        text = text.replace("SID_APP_IKS4A1_ENABLED=1", "SID_APP_IKS4A1_ENABLED=0")
    if location:
        # Location overlay: full (location-enabled) archive + feature defines.
        # The IKS5A1 define is =0 or =1 depending on the variant: match both.
        text = text.replace("sidewalk_sdk_basic", "sidewalk_sdk_full")
        text = re.sub(
            r'([ \t]*)(<listOptionValue builtIn="false" value="SID_APP_IKS5A1_ENABLED=[01]"/>)',
            r'\1\2' + "\n"
            r'\1<listOptionValue builtIn="false" value="SID_SDK_CONFIG_ENABLE_LOCATION=1"/>' + "\n"
            r'\1<listOptionValue builtIn="false" value="SID_APP_LOCATION_ENABLED=1"/>',
            text,
        )
    return text.encode("utf-8", errors="surrogateescape")


def build_environment() -> dict:
    """The SDK project runs a Python pre-build step (`python3 ... || python ...`).

    Put the interpreter running this script first on PATH so that step finds a
    real Python, even where Windows' Microsoft Store placeholders come first.
    """
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the sid_ble firmware with STM32CubeIDE's headless builder.",
        epilog="See the top of this file for what each option does.",
    )
    parser.add_argument("target", nargs="?", default="both", choices=sorted(TARGETS),
                        help="what to build (default: both MEMS shields)")
    parser.add_argument("--board", default=os.environ.get("BOARD", "wba55"),
                        help="host board: wba55 (default) or wba65")
    parser.add_argument("--location", action="store_true", default=os.environ.get("LOCATION") == "1",
                        help="add the BLE L1 location overlay to a MEMS variant")
    parser.add_argument("--stop-only", action="store_true", default=os.environ.get("LPM_STANDBY") == "0",
                        help="Stop-mode-only low power (no Standby)")
    parser.add_argument("--demo-period", default=os.environ.get("DEMO_PERIOD_S") or None, metavar="N",
                        help="counter demo uplink period in seconds")
    parser.add_argument("--cube-ide", default=os.environ.get("CUBE_IDE"), help="headless-build launcher")
    parser.add_argument("--sdk-root", default=os.environ.get("SDK_ROOT"), help="STM32-Sidewalk-SDK folder")
    args = parser.parse_args()

    board = args.board.lower()
    if board not in BOARDS:
        sys.exit(f"unknown board: {args.board} (expected: wba55 | wba65)")
    proj_sub, build_cfg, proj_name = BOARDS[board]
    if args.demo_period is not None and not str(args.demo_period).isdigit():
        sys.exit(f"--demo-period must be a whole number of seconds, got {args.demo_period!r}")

    sdk = common.find_sdk(args.sdk_root)
    cube_ide = find_cube_ide(args.cube_ide)
    print(f"CubeIDE    : {cube_ide}")
    print(f"SDK        : {sdk}")

    app = sdk / "apps" / "st" / "stm32wba" / "sid_ble"
    proj_dir = app / "STM32CubeIDE" / proj_sub
    cproject = proj_dir / ".cproject"
    app_conf = app / "Config" / "app_conf.h"
    app_sidewalk = app / "STM32_WPAN" / "App" / "app_sidewalk.c"
    if not proj_dir.is_dir():
        sys.exit(f"SDK project dir not found at {proj_dir}")
    if b"SID_APP_IKS4A1_ENABLED" not in cproject.read_bytes():
        sys.exit("The SDK has not been prepared for this demo yet. Run first:\n    python scripts/prepare-sdk.py")

    # The location-only target always needs the location overlay.
    location = args.location or args.target == "location"
    if location:
        app_dir = app / "STM32_WPAN" / "App"
        if not (app_dir / "location_wba55.c").is_file():
            sys.exit(f"Location build requested but {app_dir / 'location_wba55.c'} is missing.\n"
                     "Apply the location overlay first: examples/sidewalk-location-wba55/firmware/README.md")
        if b"location_wba55_init" not in app_sidewalk.read_bytes():
            sys.exit("Location build requested but app_sidewalk.c has no location hooks.\n"
                     "Apply the guarded hooks: examples/sidewalk-location-wba55/firmware/README.md")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    backups = {path: path.read_bytes() for path in (cproject, app_conf, app_sidewalk)}
    env = build_environment()
    built: list[Path] = []
    try:
        if args.demo_period is not None:
            substitute(app_sidewalk,
                       "#define DEMO_MESSAGE_DELAY_MS        (2u * 60000u)",
                       f"#define DEMO_MESSAGE_DELAY_MS        ({args.demo_period}u * 1000u)",
                       "DEMO_MESSAGE_DELAY_MS")
            print(f"Demo period: {args.demo_period} s (DEMO_MESSAGE_DELAY_MS)")
        if args.stop_only:
            # Stop-mode-only low power: no Standby entry, so no reset-vector wake-ups.
            substitute(app_conf, "#define CFG_LPM_STDBY_SUPPORTED  (1)", "#define CFG_LPM_STDBY_SUPPORTED  (0)",
                       "CFG_LPM_STDBY_SUPPORTED=0")
            print("LPM        : Stop-only (CFG_LPM_STDBY_SUPPORTED=0)")

        for variant in TARGETS[args.target]:
            suffix = variant
            if variant != "location" and location:
                suffix += "_loc"
            if args.stop_only:
                suffix += "_stop"
            if args.demo_period is not None:
                suffix += f"_p{args.demo_period}"

            cproject.write_bytes(configure_cproject(backups[cproject], variant, location))

            print(f"== building {board} {suffix} ==", flush=True)
            # A workspace left over from a build against a different SDK path makes
            # the import fail (same project name, different location), so start clean.
            workspace = Path(tempfile.gettempdir()) / f"{board}_ws_{suffix}"
            shutil.rmtree(workspace, ignore_errors=True)
            hex_file = proj_dir / build_cfg / f"{proj_name}.hex"
            if hex_file.exists():
                hex_file.unlink()          # never pick up a hex left by an earlier build
            log = OUT_DIR / f"build_{proj_name}_{suffix}.log"
            with open(log, "wb") as log_file:
                subprocess.run(
                    [str(cube_ide), "-data", str(workspace), "-import", str(proj_dir),
                     "-cleanBuild", f"{proj_name}/{build_cfg}", "-no-indexer"],
                    stdout=log_file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                )
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            finished = [line for line in lines if "Build Finished" in line]
            if not finished or not hex_file.is_file():
                print("build FAILED -- compiler errors:", file=sys.stderr)
                errors = [line for line in lines if ERROR_LINE.search(line)] or lines[-20:]
                for line in errors:
                    print(line, file=sys.stderr)
                print(f"full log: {log}", file=sys.stderr)
                return 1
            print(finished[-1])

            output = OUT_DIR / f"{proj_name}_{suffix}.hex"
            shutil.copyfile(hex_file, output)
            print(f"wrote {output}")
            built.append(output)
    finally:
        for path, content in backups.items():
            path.write_bytes(content)

    print()
    for output in built:
        print(f"{output.stat().st_size:>10}  {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
