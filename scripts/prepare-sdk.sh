#!/usr/bin/env bash
# Prepare a fresh STM32-Sidewalk-SDK download for the MEMS demo build.
#
# The public SDK ships without everything this example needs. This script
# stages all of it in one go so build-firmware.sh works on a pristine SDK:
#
#   1. Applies scripts/sdk-overlay/sid_ble_mems.patch to the SDK (CubeIDE
#      project wiring for both Nucleo boards, the app_sidewalk.c sensor/command
#      hooks, HAL_I2C enable, keep-SWD-alive-in-low-power, and the .thumb_func
#      directives GCC 14 needs in the reset-handler assembly).
#   2. Copies the IKS4A1 / IKS5A1 BSP and sensor component drivers from ST's
#      X-CUBE-MEMS1 package, wrapping each board's BSP .c files in a
#      SID_APP_IKSnA1_ENABLED guard so both can live in the project tree.
#   3. Copies this repo's overlay sources (sensor task, command dispatch, BSP
#      config, I2C bus glue, MLC configs) from examples/sidewalk-mems-wba55/.
#   4. Copies the CMOX headers and library from ST's X-CUBE-CRYPTOLIB package.
#
# Usage:
#   ./scripts/prepare-sdk.sh
#
# The three ST packages are auto-detected next to this repo, in ~/Downloads,
# or in ~/dev/sidewalk, under either the name the download extracts to or the
# product name. Override any of them explicitly:
#   SDK_ROOT=...   MEMS1_ROOT=...   CMOX_ROOT=...   ./scripts/prepare-sdk.sh
#
# Safe to re-run: the patch is skipped once applied and copies are idempotent.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OVERLAY="$REPO_ROOT/examples/sidewalk-mems-wba55/firmware"
PATCH="$REPO_ROOT/scripts/sdk-overlay/sid_ble_mems.patch"

SEARCH_BASES=("$(dirname "$REPO_ROOT")" "$HOME/Downloads" "$HOME/dev/sidewalk" "$HOME")

# find_pkg <label> <env-override> <verify-subpath> <name-glob>...
# Prints the first directory whose <verify-subpath> exists.
find_pkg() {
    local label="$1" override="$2" verify="$3"; shift 3
    local base glob d
    if [[ -n "$override" ]]; then
        [[ -e "$override/$verify" ]] && { echo "$override"; return 0; }
        echo "error: $label override does not look right: $override (missing $verify)" >&2
        return 1
    fi
    for base in "${SEARCH_BASES[@]}"; do
        for glob in "$@"; do
            for d in "$base"/$glob; do
                [[ -e "$d/$verify" ]] && { echo "$d"; return 0; }
            done
        done
    done
    return 1
}

fail_missing() {
    local label="$1" url="$2" var="$3"; shift 3
    {
        echo "error: could not find $label."
        echo
        echo "Download it from"
        echo "    $url"
        echo "and extract it next to this repo (or into ~/Downloads). Looked for:"
        printf '    %s\n' "$@"
        echo "or point $var at it explicitly."
    } >&2
    exit 1
}

SDK_ROOT="$(find_pkg "STM32-Sidewalk-SDK" "${SDK_ROOT:-}" \
    "apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/.cproject" \
    "STM32-Sidewalk-SDK" "STM32-Sidewalk-SDK-main")" \
    || fail_missing "the STM32-Sidewalk-SDK" \
        "https://github.com/stm32-hotspot/STM32-Sidewalk-SDK/archive/refs/heads/main.zip" \
        SDK_ROOT "STM32-Sidewalk-SDK-main/" "STM32-Sidewalk-SDK/"

MEMS1_ROOT="$(find_pkg "X-CUBE-MEMS1" "${MEMS1_ROOT:-}" \
    "Drivers/BSP/IKS4A1/iks4a1_motion_sensors.c" \
    "X-CUBE-MEMS1*" "STM32CubeExpansion_MEMS1*" "en.x-cube-mems1*")" \
    || fail_missing "X-CUBE-MEMS1 (MEMS sensor drivers)" \
        "https://www.st.com/en/embedded-software/x-cube-mems1.html" \
        MEMS1_ROOT "STM32CubeExpansion_MEMS1_V*/" "X-CUBE-MEMS1/"

CMOX_ROOT="$(find_pkg "X-CUBE-CRYPTOLIB" "${CMOX_ROOT:-}" \
    "Middlewares/ST/STM32_Cryptographic/include/cmox_init.h" \
    "X-CUBE-CRYPTOLIB*" "STM32CubeExpansion_Crypto*" "en.x-cube-cryptolib*")" \
    || fail_missing "X-CUBE-CRYPTOLIB (CMOX)" \
        "https://www.st.com/en/embedded-software/x-cube-cryptolib.html" \
        CMOX_ROOT "STM32CubeExpansion_Crypto_V*/" "X-CUBE-CRYPTOLIB/"

[[ -f "$PATCH" ]] || { echo "error: overlay patch missing: $PATCH" >&2; exit 1; }
[[ -d "$OVERLAY" ]] || { echo "error: overlay sources missing: $OVERLAY" >&2; exit 1; }

echo "SDK      : $SDK_ROOT"
echo "MEMS1    : $MEMS1_ROOT"
echo "CMOX     : $CMOX_ROOT"
echo

APP="$SDK_ROOT/apps/st/stm32wba/sid_ble"
BSP="$APP/Drivers/BSP"
CRYPTO="$SDK_ROOT/platform/sid_mcu/st/stm32common/Middlewares/ST/STM32_Cryptographic"

# --- 1. project + app patch ---------------------------------------------------
# The patch also carries a GCC 14 fix for the SDK's reset-handler assembly
# (.thumb_func on three symbols); without it the link fails on current
# CubeIDE with "Unknown destination type (ARM/Thumb)". Apply per file so a
# tree that already has the sid_ble part still receives that fix.
RESET_S="platform/sid_mcu/st/stm32wba/Projects/Common/WPAN/Startup/stm32wbaxx_ResetHandler_GCC.s"
apply_patch() {  # apply_patch [--include=<glob>]
    if command -v git >/dev/null 2>&1; then
        (cd "$SDK_ROOT" && git apply --whitespace=nowarn "$@" "$PATCH")
    else
        (cd "$SDK_ROOT" && patch -p1 --no-backup-if-mismatch < "$PATCH")
    fi
}
if grep -q "SID_APP_IKS4A1_ENABLED" "$APP/STM32CubeIDE/STM32WBA55/.cproject"; then
    if grep -q "thumb_func" "$SDK_ROOT/$RESET_S"; then
        echo "[1/4] patch already applied"
    else
        echo "[1/4] sid_ble already patched; adding the reset-handler GCC 14 fix"
        apply_patch --include="*stm32wbaxx_ResetHandler_GCC.s"
    fi
else
    echo "[1/4] applying sid_ble_mems.patch"
    apply_patch
fi

# --- 2. X-CUBE-MEMS1 BSP + component drivers ---------------------------------
# Wrap a BSP .c file so it only compiles when its board is the selected one;
# the IKS4A1 and IKS5A1 BSPs define the same global symbols.
guard_wrap() {
    local file="$1" macro="$2" tmp
    grep -q "Mutual exclusion guard" "$file" && return 0
    tmp="$(mktemp)"
    {
        printf '/* Mutual exclusion guard for the sid_ble app: only this board'"'"'s BSP\n'
        printf ' * compiles into the binary at a time. Avoids EnvCompObj/MotionCompObj\n'
        printf ' * symbol collisions with the other IKSnA1 BSP folder. */\n'
        printf '#if defined(%s) && (%s == 1)\n\n' "$macro" "$macro"
        cat "$file"
        printf '\n#endif /* %s */\n' "$macro"
    } > "$tmp"
    mv "$tmp" "$file"
}

echo "[2/4] copying X-CUBE-MEMS1 drivers"
for board in IKS4A1 IKS5A1; do
    lower="${board,,}"
    mkdir -p "$BSP/$board"
    for part in env_sensors env_sensors_ex motion_sensors motion_sensors_ex; do
        cp "$MEMS1_ROOT/Drivers/BSP/$board/${lower}_${part}.c" "$BSP/$board/"
        cp "$MEMS1_ROOT/Drivers/BSP/$board/${lower}_${part}.h" "$BSP/$board/"
        guard_wrap "$BSP/$board/${lower}_${part}.c" "SID_APP_${board}_ENABLED"
    done
done
# Only the component drivers the project's include paths reference. The
# hybrid-sensor BSP files are deliberately not copied: they #error unless a
# hybrid sensor is selected, and this demo uses none.
COMPONENTS=(Common iis2dulpx iis2mdc ilps22qs ism330is ism6hg256x lis2duxs12 lps22df lsm6dsv16x sht40ad1b stts22h)
mkdir -p "$BSP/Components"
for c in "${COMPONENTS[@]}"; do
    rm -rf "$BSP/Components/$c"
    cp -r "$MEMS1_ROOT/Drivers/BSP/Components/$c" "$BSP/Components/"
done

# --- 3. this repo's overlay sources ------------------------------------------
echo "[3/4] copying overlay sources from examples/sidewalk-mems-wba55/firmware"
cp -r "$OVERLAY/Drivers/BSP/." "$BSP/"
cp "$OVERLAY"/STM32_WPAN/App/*.[ch] "$APP/STM32_WPAN/App/"
cp "$OVERLAY"/mlc/*.h "$APP/STM32_WPAN/App/"

# --- 4. CMOX ------------------------------------------------------------------
echo "[4/4] copying X-CUBE-CRYPTOLIB (CMOX) include/ and lib/"
mkdir -p "$CRYPTO"
rm -rf "$CRYPTO/include" "$CRYPTO/lib"
cp -r "$CMOX_ROOT/Middlewares/ST/STM32_Cryptographic/include" "$CRYPTO/"
cp -r "$CMOX_ROOT/Middlewares/ST/STM32_Cryptographic/lib" "$CRYPTO/"

# --- verify -------------------------------------------------------------------
missing=0
for f in \
    "$BSP/IKS4A1/iks4a1_conf.h" "$BSP/IKS5A1/iks5a1_conf.h" \
    "$BSP/STM32WBAxx_Nucleo/stm32wbaxx_nucleo_bus.c" \
    "$BSP/Components/lsm6dsv16x/lsm6dsv16x.h" \
    "$APP/STM32_WPAN/App/sensors_iks4a1.c" "$APP/STM32_WPAN/App/sensors_iks5a1.c" \
    "$APP/STM32_WPAN/App/commands_iks4a1.c" \
    "$APP/STM32_WPAN/App/lsm6dsv16x_asset_tracking.h" \
    "$CRYPTO/include/cmox_init.h" "$CRYPTO/lib/libSTM32Cryptographic_CM33.a"
do
    [[ -f "$f" ]] || { echo "MISSING: $f" >&2; missing=1; }
done
grep -q "thumb_func" "$SDK_ROOT/$RESET_S" || { echo "MISSING: GCC 14 fix in $RESET_S" >&2; missing=1; }
[[ "$missing" == 0 ]] || exit 1

echo
echo "SDK is ready. Build with:"
echo "    ./scripts/build-firmware.sh"
