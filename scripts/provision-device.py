#!/usr/bin/env python3
"""Generate an STM32WBA Sidewalk manufacturing image from a device certificate.

Cross-platform wrapper around the STM32-Sidewalk-SDK's ``tools/provision/provision.py``.
Runs the same on Windows (PowerShell / cmd), macOS, and Linux -- unlike the
``provision-device.sh`` companion, which needs a POSIX shell.

Takes the certificate JSON downloaded from /IOTCONNECT for one wireless device
and writes the flashable manufacturing image (``mfg.bin`` / ``mfg.hex``) to
``binaries/sidewalk-mfg/<device-name>/``.

The chip argument selects the target MCU and its provisioning flash address:
    WBA55xG (default) -> 0x080FE000   (NUCLEO-WBA55CG, 1 MB)
    WBA65xI           -> 0x081FE000   (NUCLEO-WBA65RI, 2 MB)

Usage:
    python scripts/provision-device.py <device-name> <path-to-cert.json> [chip]

Examples:
    python scripts/provision-device.py StevensWBA55 certificate.json
    python scripts/provision-device.py StevensWBA65 certificate.json WBA65xI

<device-name> is just the output folder name -- use the device's /IOTCONNECT
**Unique ID** so the generated image is easy to match back to the device.

The SDK is located via --sdk-root, then the SDK_ROOT environment variable, then
a short list of conventional locations next to this repository.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# Provisioning flash address per chip (matches provision.py's chip table).
MFG_ADDR_2MB = "0x081FE000"
MFG_ADDR_1MB = "0x080FE000"
CHIPS_2MB = {"WBA65xI", "WBA64xI", "WBA63xI", "WBA62xI"}

DEFAULT_CHIP = "WBA55xG"
REPO_ROOT = Path(__file__).resolve().parent.parent


def sdk_candidates() -> list[Path]:
    """Conventional STM32-Sidewalk-SDK locations, most specific first."""
    home = Path.home()
    return [
        REPO_ROOT.parent / "STM32-Sidewalk-SDK",  # sibling of this repo
        home / "dev" / "sidewalk" / "STM32-Sidewalk-SDK",
        home / "STM32-Sidewalk-SDK",
        Path.cwd() / "STM32-Sidewalk-SDK",
    ]


def find_provision_py(sdk_root: str | None) -> Path:
    """Return the SDK's provision.py, or exit with guidance on how to get it."""
    roots = [Path(sdk_root)] if sdk_root else sdk_candidates()
    for root in roots:
        script = root.expanduser() / "tools" / "provision" / "provision.py"
        if script.is_file():
            return script

    tried = "\n".join(f"    {r.expanduser()}" for r in roots)
    sys.exit(
        "error: could not find the STM32-Sidewalk-SDK.\n"
        "\n"
        "This script uses the SDK's bundled tools/provision/provision.py to build\n"
        "the manufacturing image. Download or clone the SDK from\n"
        "    https://github.com/stm32-hotspot/STM32-Sidewalk-SDK\n"
        "then re-run with --sdk-root pointing at it, or set the SDK_ROOT\n"
        "environment variable.\n"
        "\n"
        f"Looked in:\n{tried}"
    )


def check_dependencies() -> None:
    """provision.py needs pyyaml + intelhex in the interpreter running it."""
    missing = []
    for module, package in (("yaml", "pyyaml"), ("intelhex", "intelhex")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        sys.exit(
            f"error: missing Python package(s): {', '.join(missing)}\n"
            "\n"
            "Install them into the interpreter you are running this script with:\n"
            f"    {sys.executable} -m pip install {' '.join(missing)}"
        )


def restrict(path: Path) -> None:
    """Tighten permissions on POSIX; a no-op on Windows, which has no chmod."""
    if os.name == "nt":
        return
    mode = stat.S_IRWXU if path.is_dir() else stat.S_IRUSR | stat.S_IWUSR
    path.chmod(mode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a Sidewalk manufacturing image (mfg.bin / mfg.hex) "
        "from an /IOTCONNECT device certificate JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n"
        "  python scripts/provision-device.py StevensWBA55 certificate.json\n"
        "  python scripts/provision-device.py StevensWBA65 certificate.json WBA65xI",
    )
    parser.add_argument(
        "device_name",
        help="output folder name -- use the device's /IOTCONNECT Unique ID",
    )
    parser.add_argument(
        "cert_json",
        help="path to the certificate JSON downloaded from /IOTCONNECT "
        "(usually named certificate.json)",
    )
    parser.add_argument(
        "chip",
        nargs="?",
        default=os.environ.get("CHIP", DEFAULT_CHIP),
        help=f"target MCU (default: {DEFAULT_CHIP}; use WBA65xI for the NUCLEO-WBA65RI)",
    )
    parser.add_argument(
        "--sdk-root",
        default=os.environ.get("SDK_ROOT"),
        help="path to the STM32-Sidewalk-SDK checkout "
        "(default: SDK_ROOT env var, else auto-detected next to this repo)",
    )
    args = parser.parse_args()

    cert_in = Path(args.cert_json).expanduser()
    if not cert_in.is_file():
        sys.exit(f"error: certificate JSON not found: {cert_in}")

    provision_py = find_provision_py(args.sdk_root)
    check_dependencies()

    mfg_addr = MFG_ADDR_2MB if args.chip in CHIPS_2MB else MFG_ADDR_1MB

    mfg_parent = REPO_ROOT / "binaries" / "sidewalk-mfg"
    out_dir = mfg_parent / args.device_name
    out_dir.mkdir(parents=True, exist_ok=True)
    restrict(mfg_parent)
    restrict(out_dir)

    cert_out = out_dir / "cert.json"
    shutil.copyfile(cert_in, cert_out)
    restrict(cert_out)

    # provision.py does `import sid_provision.run`, which resolves because Python
    # puts the script's own directory on sys.path -- so running it from out_dir works.
    result = subprocess.run(
        [
            sys.executable,
            str(provision_py),
            "st",
            "aws",
            "--chip",
            args.chip,
            "--certificate_json",
            "cert.json",
            "--output_bin",
            "mfg.bin",
            "--output_hex",
            "mfg.hex",
        ],
        cwd=out_dir,
    )
    if result.returncode != 0:
        return result.returncode

    for name in ("mfg.bin", "mfg.hex"):
        restrict(out_dir / name)

    print("\nwrote:")
    for item in sorted(out_dir.iterdir()):
        print(f"  {item}")
    print(f"\nChip : {args.chip}   (mfg flash address {mfg_addr})")
    print("Flash with:")
    print(f"  STM32_Programmer_CLI -c port=SWD mode=UR -d {out_dir / 'mfg.hex'} -v")
    print("or, using the raw binary and an explicit address:")
    print(
        f"  STM32_Programmer_CLI -c port=SWD mode=UR -d {out_dir / 'mfg.bin'} {mfg_addr} -v"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
