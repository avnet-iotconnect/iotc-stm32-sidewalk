#!/usr/bin/env python3
"""Prepare a fresh STM32-Sidewalk-SDK download for the MEMS demo build.

The public SDK ships without everything this example needs. This script stages
all of it in one go so build-firmware.py works on a pristine SDK:

  1. Applies scripts/sdk-overlay/sid_ble_mems.patch to the SDK (CubeIDE project
     wiring for both Nucleo boards, the app_sidewalk.c sensor/command hooks,
     HAL_I2C enable, keep-SWD-alive-in-low-power, and the .thumb_func
     directives GCC 14 needs in the reset-handler assembly).
  2. Copies the IKS4A1 / IKS5A1 BSP and sensor component drivers from ST's
     X-CUBE-MEMS1 package, wrapping each board's BSP .c files in a
     SID_APP_IKSnA1_ENABLED guard so both can live in the project tree.
  3. Copies this repo's overlay sources (sensor task, command dispatch, BSP
     config, I2C bus glue, MLC configs) from examples/sidewalk-mems-wba55/.
  4. Copies the CMOX headers and library from ST's X-CUBE-CRYPTOLIB package.

Runs the same on Windows (PowerShell / Command Prompt), macOS, and Linux. It
needs only Python: no Git, no Git Bash, no `patch` tool.

Usage:
    python scripts/prepare-sdk.py

The three ST packages are auto-detected next to this repo, in your Downloads
folder, or in ~/dev/sidewalk, under either the name the download extracts to or
the product name. Override any of them with a flag or an environment variable:
    --sdk-root / SDK_ROOT     --mems1-root / MEMS1_ROOT     --cmox-root / CMOX_ROOT

Safe to re-run: the patch is skipped once applied and copies are idempotent.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sidewalk_common as common  # noqa: E402

REPO_ROOT = common.REPO_ROOT
OVERLAY = REPO_ROOT / "examples" / "sidewalk-mems-wba55" / "firmware"
PATCH = REPO_ROOT / "scripts" / "sdk-overlay" / "sid_ble_mems.patch"
RESET_S = "platform/sid_mcu/st/stm32wba/Projects/Common/WPAN/Startup/stm32wbaxx_ResetHandler_GCC.s"

# Only the component drivers the project's include paths reference. The
# hybrid-sensor BSP files are deliberately not copied: they #error unless a
# hybrid sensor is selected, and this demo uses none.
COMPONENTS = ("Common", "iis2dulpx", "iis2mdc", "ilps22qs", "ism330is", "ism6hg256x",
              "lis2duxs12", "lps22df", "lsm6dsv16x", "sht40ad1b", "stts22h")
BSP_PARTS = ("env_sensors", "env_sensors_ex", "motion_sensors", "motion_sensors_ex")


def contains(path: Path, text: str) -> bool:
    return text.encode() in path.read_bytes()


def guard_wrap(path: Path, macro: str) -> None:
    """Wrap a BSP .c file so it only compiles when its board is the selected one.

    The IKS4A1 and IKS5A1 BSPs define the same global symbols.
    """
    body = path.read_bytes()
    if b"Mutual exclusion guard" in body:
        return
    head = (
        "/* Mutual exclusion guard for the sid_ble app: only this board's BSP\n"
        " * compiles into the binary at a time. Avoids EnvCompObj/MotionCompObj\n"
        " * symbol collisions with the other IKSnA1 BSP folder. */\n"
        f"#if defined({macro}) && ({macro} == 1)\n\n"
    ).encode()
    tail = f"\n#endif /* {macro} */\n".encode()
    path.write_bytes(head + body + tail)


def replace_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage the ST packages and this demo's sources into the STM32-Sidewalk-SDK.")
    parser.add_argument("--sdk-root", default=os.environ.get("SDK_ROOT"), help="STM32-Sidewalk-SDK folder (default: auto-detected)")
    parser.add_argument("--mems1-root", default=os.environ.get("MEMS1_ROOT"), help="X-CUBE-MEMS1 folder (default: auto-detected)")
    parser.add_argument("--cmox-root", default=os.environ.get("CMOX_ROOT"), help="X-CUBE-CRYPTOLIB folder (default: auto-detected)")
    args = parser.parse_args()

    sdk = common.find_sdk(args.sdk_root)

    mems1_names = ("X-CUBE-MEMS1*", "STM32CubeExpansion_MEMS1*", "en.x-cube-mems1*")
    mems1 = common.find_package("X-CUBE-MEMS1", args.mems1_root, "Drivers/BSP/IKS4A1/iks4a1_motion_sensors.c", mems1_names)
    if mems1 is None:
        common.fail_missing("X-CUBE-MEMS1 (MEMS sensor drivers)", "https://www.st.com/en/embedded-software/x-cube-mems1.html",
                            "MEMS1_ROOT", ("STM32CubeExpansion_MEMS1_V*", "X-CUBE-MEMS1"))

    cmox_names = ("X-CUBE-CRYPTOLIB*", "STM32CubeExpansion_Crypto*", "en.x-cube-cryptolib*")
    cmox = common.find_package("X-CUBE-CRYPTOLIB", args.cmox_root, "Middlewares/ST/STM32_Cryptographic/include/cmox_init.h", cmox_names)
    if cmox is None:
        common.fail_missing("X-CUBE-CRYPTOLIB (CMOX)", "https://www.st.com/en/embedded-software/x-cube-cryptolib.html",
                            "CMOX_ROOT", ("STM32CubeExpansion_Crypto_V*", "X-CUBE-CRYPTOLIB"))

    if not PATCH.is_file():
        sys.exit(f"error: overlay patch missing: {PATCH}")
    if not OVERLAY.is_dir():
        sys.exit(f"error: overlay sources missing: {OVERLAY}")

    print(f"SDK      : {sdk}")
    print(f"MEMS1    : {mems1}")
    print(f"CMOX     : {cmox}")
    print()

    app = sdk / "apps" / "st" / "stm32wba" / "sid_ble"
    bsp = app / "Drivers" / "BSP"
    crypto = sdk / "platform" / "sid_mcu" / "st" / "stm32common" / "Middlewares" / "ST" / "STM32_Cryptographic"

    # --- 1. project + app patch ------------------------------------------------
    # The patch also carries a GCC 14 fix for the SDK's reset-handler assembly
    # (.thumb_func on three symbols); without it the link fails on current
    # CubeIDE with "Unknown destination type (ARM/Thumb)". A tree that already
    # has the sid_ble part still receives that fix.
    try:
        if contains(app / "STM32CubeIDE" / "STM32WBA55" / ".cproject", "SID_APP_IKS4A1_ENABLED"):
            if contains(sdk / RESET_S, "thumb_func"):
                print("[1/4] patch already applied")
            else:
                print("[1/4] sid_ble already patched; adding the reset-handler GCC 14 fix")
                common.apply_patch(PATCH, sdk, only="stm32wbaxx_ResetHandler_GCC.s")
        else:
            print("[1/4] applying sid_ble_mems.patch")
            common.apply_patch(PATCH, sdk)
    except common.PatchError as error:
        sys.exit(
            f"error: could not apply the overlay patch: {error}\n"
            "\n"
            "The SDK does not match the version this patch was made for. Download a\n"
            f"fresh copy from\n    {common.SDK_URL}\nand run this script again."
        )

    # --- 2. X-CUBE-MEMS1 BSP + component drivers -------------------------------
    print("[2/4] copying X-CUBE-MEMS1 drivers")
    for board in ("IKS4A1", "IKS5A1"):
        lower = board.lower()
        (bsp / board).mkdir(parents=True, exist_ok=True)
        for part in BSP_PARTS:
            for ext in (".c", ".h"):
                name = f"{lower}_{part}{ext}"
                shutil.copyfile(mems1 / "Drivers" / "BSP" / board / name, bsp / board / name)
            guard_wrap(bsp / board / f"{lower}_{part}.c", f"SID_APP_{board}_ENABLED")
    (bsp / "Components").mkdir(parents=True, exist_ok=True)
    for component in COMPONENTS:
        replace_tree(mems1 / "Drivers" / "BSP" / "Components" / component, bsp / "Components" / component)

    # --- 3. this repo's overlay sources ----------------------------------------
    print("[3/4] copying overlay sources from examples/sidewalk-mems-wba55/firmware")
    shutil.copytree(OVERLAY / "Drivers" / "BSP", bsp, dirs_exist_ok=True)
    app_src = app / "STM32_WPAN" / "App"
    for pattern in ("STM32_WPAN/App/*.c", "STM32_WPAN/App/*.h", "mlc/*.h"):
        for source in sorted(glob.glob(str(OVERLAY / pattern))):
            shutil.copyfile(source, app_src / Path(source).name)

    # --- 4. CMOX ---------------------------------------------------------------
    print("[4/4] copying X-CUBE-CRYPTOLIB (CMOX) include/ and lib/")
    crypto.mkdir(parents=True, exist_ok=True)
    for folder in ("include", "lib"):
        replace_tree(cmox / "Middlewares" / "ST" / "STM32_Cryptographic" / folder, crypto / folder)

    # --- verify ----------------------------------------------------------------
    expected = (
        bsp / "IKS4A1" / "iks4a1_conf.h", bsp / "IKS5A1" / "iks5a1_conf.h",
        bsp / "STM32WBAxx_Nucleo" / "stm32wbaxx_nucleo_bus.c",
        bsp / "Components" / "lsm6dsv16x" / "lsm6dsv16x.h",
        app_src / "sensors_iks4a1.c", app_src / "sensors_iks5a1.c",
        app_src / "commands_iks4a1.c",
        app_src / "lsm6dsv16x_asset_tracking.h",
        crypto / "include" / "cmox_init.h", crypto / "lib" / "libSTM32Cryptographic_CM33.a",
    )
    missing = [str(path) for path in expected if not path.is_file()]
    if not contains(sdk / RESET_S, "thumb_func"):
        missing.append(f"GCC 14 fix in {RESET_S}")
    if missing:
        for item in missing:
            print(f"MISSING: {item}", file=sys.stderr)
        return 1

    print()
    print("SDK is ready. Build with:")
    print("    python scripts/build-firmware.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
