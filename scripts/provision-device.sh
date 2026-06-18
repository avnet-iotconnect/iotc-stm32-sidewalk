#!/usr/bin/env bash
# Generate a STM32WBA55-compatible Sidewalk manufacturing image from a device
# cert.json (downloaded from AWS IoT Wireless during provisioning) and place it
# under iotc-stm32-sidewalk/binaries/sidewalk-mfg/<device>/.
#
# Usage:
#   ./scripts/provision-device.sh <device-name> <path-to-cert.json>
# Example:
#   ./scripts/provision-device.sh mclST5A2 ~/Downloads/mclST5A2.json

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_ROOT="${SDK_ROOT:-$HOME/dev/sidewalk/STM32-Sidewalk-SDK}"
PROVISION_PY="$SDK_ROOT/tools/provision/provision.py"

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <device-name> <path-to-cert.json>" >&2
    exit 2
fi
DEVICE="$1"
CERT_IN="$2"

[[ -f "$CERT_IN" ]] || { echo "cert.json not found: $CERT_IN" >&2; exit 1; }
[[ -f "$PROVISION_PY" ]] || { echo "provision.py not found: $PROVISION_PY" >&2; exit 1; }

OUT_DIR="$REPO_ROOT/binaries/sidewalk-mfg/$DEVICE"
mkdir -p "$OUT_DIR"
chmod 700 "$REPO_ROOT/binaries/sidewalk-mfg" "$OUT_DIR"

cp "$CERT_IN" "$OUT_DIR/cert.json"
chmod 600 "$OUT_DIR/cert.json"

cd "$OUT_DIR"
python3 "$PROVISION_PY" st aws --chip WBA55xG \
    --certificate_json cert.json \
    --output_bin mfg.bin \
    --output_hex mfg.hex

chmod 600 mfg.bin mfg.hex

echo "wrote:"
ls -la "$OUT_DIR"
echo ""
echo "Flash with:"
echo "  STM32_Programmer_CLI -c port=SWD mode=UR -d $OUT_DIR/mfg.bin 0x080FE000 -v"
