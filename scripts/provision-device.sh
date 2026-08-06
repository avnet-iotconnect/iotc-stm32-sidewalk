#!/usr/bin/env bash
# Generate a STM32WBA-compatible Sidewalk manufacturing image from a device
# cert.json (downloaded from AWS IoT Wireless during provisioning) and place it
# under iotc-stm32-sidewalk/binaries/sidewalk-mfg/<device>/.
#
# Works for both Nucleo boards — pass the chip as the optional 3rd argument
# (or CHIP env var). It selects the provisioning flash address automatically:
#   WBA55xG (default) -> 0x080FE000   (NUCLEO-WBA55CG, 1 MB)
#   WBA65xI           -> 0x081FE000   (NUCLEO-WBA65RI, 2 MB)
#
# Usage:
#   ./scripts/provision-device.sh <device-name> <path-to-cert.json> [chip]
# Examples:
#   ./scripts/provision-device.sh mclST5A2 ~/Downloads/mclST5A2.json            # WBA55xG
#   ./scripts/provision-device.sh mclST5A2 ~/Downloads/mclST5A2.json WBA65xI    # WBA65

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_ROOT="${SDK_ROOT:-$HOME/dev/sidewalk/STM32-Sidewalk-SDK}"
PROVISION_PY="$SDK_ROOT/tools/provision/provision.py"

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "usage: $0 <device-name> <path-to-cert.json> [chip]" >&2
    echo "       chip defaults to WBA55xG; use WBA65xI for the NUCLEO-WBA65RI" >&2
    exit 2
fi
DEVICE="$1"
CERT_IN="$2"
CHIP="${3:-${CHIP:-WBA55xG}}"

# Provisioning flash address per chip (matches provision.py's chip table).
case "$CHIP" in
    WBA65xI|WBA64xI|WBA63xI|WBA62xI) MFG_ADDR="0x081FE000" ;;  # 2 MB parts
    *)                               MFG_ADDR="0x080FE000" ;;  # 1 MB parts (WBA55xG, ...)
esac

[[ -f "$CERT_IN" ]] || { echo "cert.json not found: $CERT_IN" >&2; exit 1; }
[[ -f "$PROVISION_PY" ]] || { echo "provision.py not found: $PROVISION_PY" >&2; exit 1; }

OUT_DIR="$REPO_ROOT/binaries/sidewalk-mfg/$DEVICE"
mkdir -p "$OUT_DIR"
chmod 700 "$REPO_ROOT/binaries/sidewalk-mfg" "$OUT_DIR"

cp "$CERT_IN" "$OUT_DIR/cert.json"
chmod 600 "$OUT_DIR/cert.json"

cd "$OUT_DIR"
python3 "$PROVISION_PY" st aws --chip "$CHIP" \
    --certificate_json cert.json \
    --output_bin mfg.bin \
    --output_hex mfg.hex

chmod 600 mfg.bin mfg.hex

echo "wrote:"
ls -la "$OUT_DIR"
echo ""
echo "Chip : $CHIP   (mfg flash address $MFG_ADDR)"
echo "Flash with:"
echo "  STM32_Programmer_CLI -c port=SWD mode=UR -d $OUT_DIR/mfg.bin $MFG_ADDR -v"
