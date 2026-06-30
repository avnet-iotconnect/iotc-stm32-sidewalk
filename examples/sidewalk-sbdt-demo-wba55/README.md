# sid_sbdt_demo — Build & Flash Notes

Board: NUCLEO-WBA55CG (BLE-only, no Sub-GHz radio required)  
SDK: STM32-Sidewalk-SDK

> **Pre-built binaries are not distributed in this repository.** The
> three hex files that make up the demo (the AIM secure bootloader, the
> signed SBDT demo application, and the OTA-delivery image) incorporate
> compiled code from X-CUBE-CRYPTOLIB (CMOX) and the Amazon Sidewalk SDK,
> whose upstream licenses constrain binary redistribution. See
> [../../NOTICE.md](../../NOTICE.md) for the SBOM. Workshop participants
> receive pre-flashed boards from the facilitator; everyone else rebuilds
> the artifacts locally per the instructions below.

---

## Files referenced by this guide (produced locally — not committed)

| File | Description | Flash? |
|---|---|---|
| `sid_application_install_manager_stm32wba55.hex` | AIM secure bootloader | Yes — first |
| `sid_sbdt_demo_wba55.hex` | SBDT demo application (signed) | Yes — second |
| `mfg.hex` | Sidewalk provisioning image (device credentials) | Yes — third |
| `mfg.bin` | Same credentials in binary form (alternative flash method) | Optional |
| `sid_sbdt_demo_wba55_ota_image.hex` | Signed OTA payload — sent to device over Sidewalk SBDT | Do not flash directly |
| `application_signing_key.pem` | Ed25519 private key used to sign the firmware | Keep safe — not flashed |

All of the above land in this directory after you complete the build
steps in **Rebuilding from source** below and the provisioning step at
the end of the same section.

---

## Flash order (STM32CubeProgrammer CLI)

After completing the local build, connect ST-LINK to the NUCLEO-WBA55CG, then run these commands in order:

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

> **Note:** `mfg.hex` flashes to address `0x080FE000`. If using the binary form instead:
> ```bash
> STM32_Programmer_CLI -c port=SWD mode=UR -d mfg.bin 0x080FE000 -v -rst
> ```

---

## What each image does at runtime

1. On every power-on/reset, the **AIM bootloader** runs first. It verifies the application's Ed25519 signature and CRC, then jumps to the application.
2. The **SBDT demo application** starts, initialises Sidewalk over BLE, and waits for a Sidewalk Bulk Data Transfer (SBDT) session from the cloud.
3. When an OTA update is triggered, the cloud sends `sid_sbdt_demo_wba55_ota_image.hex` to the device over Sidewalk. The device writes it to the staging flash slot and reboots.
4. AIM verifies the new image, installs it block-by-block (with rollback backup), then boots into it.
5. If the new firmware fails to confirm itself within the boot limit, AIM automatically rolls back to the previous version.

---

## Signing key notes

`application_signing_key.pem` contains the Ed25519 **private key** used to sign the firmware during build. The corresponding **public key** is compiled into `sid_application_install_manager_stm32wba55.hex`.

**These two must stay in sync.** If AIM is rebuilt without this `.pem`, it will embed a new public key and reject the existing signed application hex — requiring a full rebuild and reflash of both images.

---

## Rebuilding from source

Prerequisites on the build machine:
- STM32CubeIDE 1.18.1 at `/opt/st/stm32cubeide_1.18.1/`
- STM32-Sidewalk-SDK at `/root/ws/STM32-Sidewalk-SDK`
- `pynacl~=1.6` installed (`pip3 install --break-system-packages pynacl`)
- `cmox_small_config.h` copied from `STM32CubeExpansion_Crypto_V5.0.0/Middlewares/ST/STM32_Cryptographic/templates/` into the SDK crypto include dir

```bash
# 1 — AIM bootloader (generates/reuses application_signing_key.pem)
# Output: .../sid_application_install_manager/STM32CubeIDE/STM32WBA55/Debug/sid_application_install_manager_stm32wba55.hex
/opt/st/stm32cubeide_1.18.1/headless-build.sh \
  -data /tmp/aim_ws \
  -import /root/ws/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_application_install_manager/STM32CubeIDE/STM32WBA55 \
  -cleanBuild "sid_application_install_manager_stm32wba55/Debug" \
  -no-indexer

# 2 — SBDT demo (auto-signed with the key above)
# Output: .../sid_sbdt_demo/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_sbdt_demo_wba55.hex
#         .../sid_sbdt_demo/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_sbdt_demo_wba55_ota_image.hex
/opt/st/stm32cubeide_1.18.1/headless-build.sh \
  -data /tmp/sbdt_ws \
  -import /root/ws/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_sbdt_demo/STM32CubeIDE/STM32WBA55 \
  -cleanBuild "sid_sbdt_demo_wba55/Debug_Nucleo-WBA55" \
  -no-indexer

# 3 — Provisioning image (regenerate if using a different device JSON)
# Output goes directly into this binaries folder
cd /root/ws/iotc-stm32-sidewalk/binaries/sid_sbdt_demo
python3 /root/ws/STM32-Sidewalk-SDK/tools/provision/provision.py \
  st aws --chip WBA55xG \
  --certificate_json /root/ws/iotc-stm32-sidewalk/StSidewalk5.json \
  --output_bin mfg.bin \
  --output_hex mfg.hex
```
