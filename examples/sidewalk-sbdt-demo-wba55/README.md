# sid_sbdt_demo — Build & Flash Notes

Boards: NUCLEO-WBA55CG (STM32WBA55CG, 1 MB flash) or NUCLEO-WBA65RI (STM32WBA65RI, 2 MB flash) — both BLE-only, no Sub-GHz radio required  
SDK: STM32-Sidewalk-SDK

> This guide covers **both** boards. Where the two differ, the WBA65
> equivalent is shown compactly alongside the WBA55 default. The
> STM32-Sidewalk-SDK already ships STM32WBA65 CubeIDE projects for both
> apps used here (`sid_application_install_manager_stm32wba65` and
> `sid_sbdt_demo_wba65`, the latter with `Debug_Nucleo-WBA65` /
> `Release_Nucleo-WBA65` configs), so no new SDK project is needed.

> **Pre-built binaries are not distributed in this repository.** The
> three hex files that make up the demo (the AIM secure bootloader, the
> signed SBDT demo application, and the OTA-delivery image) incorporate
> compiled code from X-CUBE-CRYPTOLIB (CMOX) and the Amazon Sidewalk SDK,
> whose upstream licenses constrain binary redistribution. See
> [../../NOTICE.md](../../NOTICE.md) for the SBOM. Rebuild the artifacts
> locally per the instructions below.

---

## Files referenced by this guide (produced locally — not committed)

Filenames below are for WBA55; the WBA65 equivalent is listed next to each.

| File (WBA55) | File (WBA65) | Description | Flash? |
|---|---|---|---|
| `sid_application_install_manager_stm32wba55.hex` | `sid_application_install_manager_stm32wba65.hex` | AIM secure bootloader | Yes — first |
| `sid_sbdt_demo_wba55.hex` | `sid_sbdt_demo_wba65.hex` | SBDT demo application (signed) | Yes — second |
| `mfg.hex` | `mfg.hex` | Sidewalk provisioning image (device credentials) | Yes — third |
| `mfg.bin` | `mfg.bin` | Same credentials in binary form (alternative flash method) | Optional |
| `sid_sbdt_demo_wba55_ota_image.hex` | `sid_sbdt_demo_wba65_ota_image.hex` | Signed OTA payload — sent to device over Sidewalk SBDT | Do not flash directly |
| `application_signing_key.pem` | `application_signing_key.pem` | Ed25519 private key used to sign the firmware | Keep safe — not flashed |

All of the above land in this directory after you complete the build
steps in **Rebuilding from source** below and the provisioning step at
the end of the same section.

---

## Flash order (STM32CubeProgrammer CLI)

After completing the local build, connect ST-LINK to the NUCLEO-WBA55CG (or NUCLEO-WBA65RI), then run these commands in order. The commands below use the WBA55 hex names; for WBA65 substitute the `_wba65` filenames from the table above.

```bash
# 0. Full chip erase (do this first, every time)
STM32_Programmer_CLI -c port=SWD mode=UR -e all

# 1. AIM secure bootloader
STM32_Programmer_CLI -c port=SWD mode=UR -d sid_application_install_manager_stm32wba55.hex -v

# 2. SBDT demo application
STM32_Programmer_CLI -c port=SWD mode=UR -d sid_sbdt_demo_wba55.hex -v

# 3. Sidewalk provisioning (device credentials) — reset after this
STM32_Programmer_CLI -c port=SWD mode=UR -d mfg.hex -v -rst
```

> **Note:** `mfg.hex` carries its own flash address, so the same command works on both boards. If using the binary form instead, the address is board-specific:
> ```bash
> # WBA55
> STM32_Programmer_CLI -c port=SWD mode=UR -d mfg.bin 0x080FE000 -v -rst
> # WBA65
> STM32_Programmer_CLI -c port=SWD mode=UR -d mfg.bin 0x081FE000 -v -rst
> ```

---

## What each image does at runtime

1. On every power-on/reset, the **AIM bootloader** runs first. It verifies the application's Ed25519 signature and CRC, then jumps to the application.
2. The **SBDT demo application** starts, initialises Sidewalk over BLE, and waits for a Sidewalk Bulk Data Transfer (SBDT) session from the cloud.
3. When an OTA update is triggered, the cloud sends the OTA image (`sid_sbdt_demo_wba55_ota_image.hex`, or `sid_sbdt_demo_wba65_ota_image.hex` on WBA65) to the device over Sidewalk. The device writes it to the staging flash slot and reboots.
4. AIM verifies the new image, installs it block-by-block (with rollback backup), then boots into it.
5. If the new firmware fails to confirm itself within the boot limit, AIM automatically rolls back to the previous version.

---

## Signing key notes

`application_signing_key.pem` contains the Ed25519 **private key** used to sign the firmware during build. The corresponding **public key** is compiled into the AIM bootloader hex (`sid_application_install_manager_stm32wba55.hex`, or `sid_application_install_manager_stm32wba65.hex` on WBA65). This mechanism is identical on both boards.

**These two must stay in sync.** If AIM is rebuilt without this `.pem`, it will embed a new public key and reject the existing signed application hex — requiring a full rebuild and reflash of both images.

---

## Rebuilding from source

Prerequisites on the build machine:
- STM32CubeIDE 1.18.1 at `/opt/st/stm32cubeide_1.18.1/`
- STM32-Sidewalk-SDK at `/root/ws/STM32-Sidewalk-SDK`
- `pynacl~=1.6` installed (`pip3 install --break-system-packages pynacl`)
- `cmox_small_config.h` copied from `STM32CubeExpansion_Crypto_V5.0.0/Middlewares/ST/STM32_Cryptographic/templates/` into the SDK crypto include dir

The commands below build for **WBA55**. To build for **WBA65** instead, swap the CubeIDE project directory (`STM32WBA55` → `STM32WBA65`), the build-config/project names, and the provision `--chip` value as noted inline.

```bash
# 1 — AIM bootloader (generates/reuses application_signing_key.pem)
# Output: .../sid_application_install_manager/STM32CubeIDE/STM32WBA55/Debug/sid_application_install_manager_stm32wba55.hex
/opt/st/stm32cubeide_1.18.1/headless-build.sh \
  -data /tmp/aim_ws \
  -import /root/ws/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_application_install_manager/STM32CubeIDE/STM32WBA55 \
  -cleanBuild "sid_application_install_manager_stm32wba55/Debug" \
  -no-indexer
# WBA65: -import .../sid_application_install_manager/STM32CubeIDE/STM32WBA65
#        -cleanBuild "sid_application_install_manager_stm32wba65/Debug"
#        (AIM has no per-board Nucleo config; the STM32WBA65 project builds the WBA65 AIM)

# 2 — SBDT demo (auto-signed with the key above)
# Output: .../sid_sbdt_demo/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_sbdt_demo_wba55.hex
#         .../sid_sbdt_demo/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_sbdt_demo_wba55_ota_image.hex
/opt/st/stm32cubeide_1.18.1/headless-build.sh \
  -data /tmp/sbdt_ws \
  -import /root/ws/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_sbdt_demo/STM32CubeIDE/STM32WBA55 \
  -cleanBuild "sid_sbdt_demo_wba55/Debug_Nucleo-WBA55" \
  -no-indexer
# WBA65: -import .../sid_sbdt_demo/STM32CubeIDE/STM32WBA65
#        -cleanBuild "sid_sbdt_demo_wba65/Debug_Nucleo-WBA65"
#        (Release_Nucleo-WBA65 is also available; outputs are the _wba65 hex names)

# 3 — Provisioning image (regenerate if using a different device JSON)
# Output goes directly into this binaries folder
cd /root/ws/iotc-stm32-sidewalk/binaries/sid_sbdt_demo
python3 /root/ws/STM32-Sidewalk-SDK/tools/provision/provision.py \
  st aws --chip WBA55xG \
  --certificate_json /root/ws/iotc-stm32-sidewalk/StSidewalk5.json \
  --output_bin mfg.bin \
  --output_hex mfg.hex
# WBA65: use --chip WBA65xI (all other arguments unchanged)
```
