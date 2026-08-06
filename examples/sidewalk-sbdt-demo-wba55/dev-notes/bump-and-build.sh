#!/usr/bin/env bash
# Bump the sid_sbdt_demo app version, rebuild, and stage the OTA image for the next
# FUOTA test round. One command per test iteration.
#
# Usage:
#   ./bump-and-build.sh            # auto-increment the patch  (e.g. 1.1.2 -> 1.1.3)
#   ./bump-and-build.sh 1.2.0      # set an explicit version
#
# When it finishes, upload the printed *_ota_image.bin to your S3 FUOTA path and trigger
# the task. Keep the device on the PREVIOUS version (don't SWD-flash) so the OTA is a real
# upgrade with a visible version change.
set -euo pipefail

SDK="/home/mlamp/dev/sidewalk/STM32-Sidewalk-SDK"
VERDEF="$SDK/apps/st/common/build_system/stm32_sidewalk_sdk_version.def"
BD="$SDK/apps/st/stm32wba/sid_sbdt_demo/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55"
DST="/home/mlamp/dev/sidewalk/iotc-stm32-sidewalk/binaries/sid_sbdt_demo"
TC="/opt/st/stm32cubeide_1.18.0/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.13.3.rel1.linux64_1.0.0.202410170706/tools/bin"
PATCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ota_status_appversion_versionbump.patch"

cur="$(grep -oE 'STM32WBA_APPS_PACKAGE_VER := [0-9]+\.[0-9]+\.[0-9]+' "$VERDEF" | awk '{print $3}')"
[ -n "$cur" ] || { echo "Could not read current version from $VERDEF"; exit 1; }

if [ $# -ge 1 ]; then
    new="$1"
    [[ "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Version must be MAJOR.MINOR.PATCH, got '$new'"; exit 1; }
else
    IFS='.' read -r a b c <<< "$cur"
    new="$a.$b.$((c + 1))"
fi

echo ">> Version: $cur -> $new"
sed -i "s/STM32WBA_APPS_PACKAGE_VER := $cur/STM32WBA_APPS_PACKAGE_VER := $new/" "$VERDEF"

echo ">> Building (log: /tmp/sbdt_build.log) ..."
export PATH="$TC:$PATH"
if ! make -C "$BD" -j"$(nproc)" all >/tmp/sbdt_build.log 2>&1; then
    echo "!! BUILD FAILED:"; tail -25 /tmp/sbdt_build.log; exit 1
fi

cp "$BD/sid_sbdt_demo_wba55_ota_image.bin" "$DST/"
cp "$BD/sid_sbdt_demo_wba55_ota_image.hex" "$DST/"
cp "$BD/sid_sbdt_demo_wba55.hex"           "$DST/"

# Keep the enhancements revert patch's version hunk in sync so rollback-enhancements.sh
# still reverses cleanly (baseline stays 1.1.0; only the "+" side tracks the current version).
[ -f "$PATCH" ] && sed -i "s/^+STM32WBA_APPS_PACKAGE_VER := .*/+STM32WBA_APPS_PACKAGE_VER := $new/" "$PATCH"

echo ">> Done. Version $new built and staged:"
echo "   OTA image (upload to S3):  $DST/sid_sbdt_demo_wba55_ota_image.bin"
echo "   app hex   (SWD if needed): $DST/sid_sbdt_demo_wba55.hex"
