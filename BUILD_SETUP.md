# Build Setup: compiling the firmware yourself

Pre-built firmware is not distributed in this repository (see [`NOTICE.md`](NOTICE.md)), so the hex files in Step 9 of [Getting Started](GETTING_STARTED.md) come from a local build. This page is the one-time setup for that build. Once done, the build itself is a single command.

## 1. Install STM32CubeIDE

[STM32CubeIDE](https://www.st.com/en/development-tools/stm32cubeide.html) — you never open it, but the build script drives its headless compiler, so it must be installed. Default location is fine.

## 2. Download three packages

Extract all three **next to** the `iotc-stm32-sidewalk` folder (or leave them in `Downloads`). Keep the folder names the archives give you — no renaming needed.

| Package | Get it from | Provides |
|---|---|---|
| **STM32-Sidewalk-SDK** | [GitHub ZIP](https://github.com/stm32-hotspot/STM32-Sidewalk-SDK/archive/refs/heads/main.zip) (public, ~53 MB) | The Sidewalk stack and the `sid_ble` app this demo builds on |
| **X-CUBE-MEMS1** | [st.com](https://www.st.com/en/embedded-software/x-cube-mems1.html) (free ST account) | Drivers for the sensors on the IKS4A1 / IKS5A1 shields |
| **X-CUBE-CRYPTOLIB** | [st.com](https://www.st.com/en/embedded-software/x-cube-cryptolib.html) (free ST account; accept the click-through licence) | The CMOX crypto library the Sidewalk SDK links against |

Expected layout:

```
Downloads/
├── iotc-stm32-sidewalk-main/
├── STM32-Sidewalk-SDK-main/
├── STM32CubeExpansion_MEMS1_V…/
└── STM32CubeExpansion_Crypto_V…/
```

## 3. Prepare the SDK (once)

The public SDK ships without the sensor drivers, the crypto library, or this demo's sources. One script stages all of it — from Git Bash on Windows, or any shell on macOS/Linux:

```bash
./scripts/prepare-sdk.sh
```

It finds the three packages automatically and prints what it used. If you keep one somewhere unusual, point at it: `SDK_ROOT=… MEMS1_ROOT=… CMOX_ROOT=… ./scripts/prepare-sdk.sh`. Safe to re-run.

## 4. Build

```bash
./scripts/build-firmware.sh           # both sensor shields (WBA55)
./scripts/build-firmware.sh iks4a1    # one shield only
BOARD=wba65 ./scripts/build-firmware.sh   # NUCLEO-WBA65RI instead
```

Output lands in `binaries/`, e.g. `binaries/sid_ble_wba55_iks4a1.hex`. Return to [Getting Started, Step 9](GETTING_STARTED.md#9-build-and-flash-the-firmware) to flash it.

## If it fails

| Message | Cause | Fix |
|---|---|---|
| `could not find …` from `prepare-sdk.sh` | A package is missing or somewhere the script does not look | The error lists every path it tried; extract the package there, or set the matching `…_ROOT` variable |
| `STM32CubeIDE headless build not found` | CubeIDE not installed, or in a non-default location | Install it, or `CUBE_IDE=/path/to/headless-build.bat ./scripts/build-firmware.sh` |
| `iks4a1_motion_sensors.h: No such file` / `cmox_init.h: No such file` | Step 3 was skipped, or the SDK was re-extracted afterwards | Run `./scripts/prepare-sdk.sh` again |
| `Unknown destination type (ARM/Thumb)` at link | SDK missing the GCC 14 reset-handler fix | Run `./scripts/prepare-sdk.sh` again — it applies the fix even to an SDK that was prepared earlier |

Every build writes a full log to `binaries/build_<project>_<variant>.log`; on failure the script prints the compiler errors from it.

## What `prepare-sdk.sh` actually does

For anyone who wants to reproduce it by hand, or build from the CubeIDE GUI instead:

1. Applies [`scripts/sdk-overlay/sid_ble_mems.patch`](scripts/sdk-overlay/sid_ble_mems.patch) to the SDK — CubeIDE project wiring for both Nucleo boards, the sensor/command hooks in `app_sidewalk.c`, `HAL_I2C_MODULE_ENABLED`, keep-SWD-reachable-in-low-power, and the GCC 14 `.thumb_func` fix.
2. Copies the IKS4A1 and IKS5A1 BSP sources and the needed sensor component drivers from X-CUBE-MEMS1 into `sid_ble/Drivers/BSP/`, wrapping each board's BSP `.c` files in a `SID_APP_IKSnA1_ENABLED` guard so both can coexist.
3. Copies this repo's overlay from [`examples/sidewalk-mems-wba55/firmware/`](examples/sidewalk-mems-wba55/firmware/) — sensor task, command dispatch, BSP config, I²C bus glue, MLC configs.
4. Copies the CMOX `include/` and `lib/` from X-CUBE-CRYPTOLIB into the SDK's `STM32_Cryptographic/` middleware folder.

The [example README](examples/sidewalk-mems-wba55/README.md) covers the firmware design, wire format, and GUI build in depth.
