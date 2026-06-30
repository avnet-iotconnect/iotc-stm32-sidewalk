# NOTICE

This repository's `LICENSE` (MIT) covers the original Avnet /IOTCONNECT
content: device-side decoders, dashboard templates, helper scripts, build
documentation, READMEs, and original firmware source files written for this
demo (notably `examples/*/firmware/STM32_WPAN/App/sensors_*.c`,
`commands_*.c`, `location_wba55.c`).

The remainder of this repository — pre-built firmware images, BSP source
files originally derived from STMicroelectronics templates, and the
LSM6DSV16X MLC configuration files — incorporates work covered by upstream
third-party licenses. The MIT terms above DO NOT relicense or supersede
those upstream terms. The following Software Bill of Materials (SBOM)
documents them.

---

## Software Bill of Materials (SBOM)

### Source files committed to this repository

| Path | Upstream component | Upstream license | Upstream copyright holder |
|---|---|---|---|
| `examples/sidewalk-mems-wba55/firmware/mlc/lsm6dsv16x_asset_tracking.h` | STMems_Machine_Learning_Core | BSD-3-Clause | STMicroelectronics |
| `examples/sidewalk-mems-wba55/firmware/mlc/lsm6dsv16x_asset_tracking.ucf` | STMems_Machine_Learning_Core | BSD-3-Clause | STMicroelectronics |
| `examples/sidewalk-mems-wba55/firmware/Drivers/BSP/IKS4A1/iks4a1_conf.h` | X-CUBE-MEMS1 (BSP, derived) | BSD-3-Clause | STMicroelectronics |
| `examples/sidewalk-mems-wba55/firmware/Drivers/BSP/IKS5A1/iks5a1_conf.h` | X-CUBE-MEMS1 (BSP, derived) | BSD-3-Clause | STMicroelectronics |
| `examples/sidewalk-mems-wba55/firmware/Drivers/BSP/STM32WBAxx_Nucleo/stm32wbaxx_nucleo_bus.{c,h}` | STM32WBAxx_Nucleo BSP (derived) | BSD-3-Clause | STMicroelectronics |
| Every other `examples/*/firmware/**/*.{c,h}` | Original Avnet content | MIT (see LICENSE) | Avnet /IOTCONNECT |
| `decoders/*.py`, `scripts/*`, `tools/*`, `device-templates/*` | Original Avnet content | MIT (see LICENSE) | Avnet /IOTCONNECT |

### Components linked into the pre-built firmware images (`binaries/`, `examples/*/*.hex`)

Authoritative SBOM source: `STM32-Sidewalk-SDK/LICENSE.md`. Each component
is governed by its own upstream license; the MIT terms of this repository
do not override them. The list below is reproduced from the upstream SDK
LICENSE for end-user reference.

| Component | License | Copyright holder |
|---|---|---|
| CMSIS | Apache-2.0 | Arm Limited |
| STM32WBAxx CMSIS | Apache-2.0 | Arm Limited, STMicroelectronics |
| STM32WBAxx_HAL_Driver | BSD-3-Clause | STMicroelectronics |
| BSP STM32WBAxx_Nucleo | BSD-3-Clause | STMicroelectronics |
| lib_gnss (Teseo GNSS middleware) | Annex 1 (see SDK LICENSE) | STMicroelectronics |
| STM32_Cryptographic (CMOX, middleware) | SLA (see SDK LICENSE) + X-CUBE-CRYPTOLIB click-through | STMicroelectronics |
| FreeRTOS (middleware) | MIT | Amazon.com, Inc. or its affiliates |
| lbm_lib (LoRa Basics Modem middleware) | Annex 3 (see SDK LICENSE) | Semtech, STMicroelectronics |
| littlefs (filesystem middleware) | BSD-3-Clause | The littlefs authors, Arm Limited |
| STM32_WPAN (BLE, Linklayer) | SLA (see SDK LICENSE) | STMicroelectronics, Synopsys |
| SubGHz_Phy (middleware) | Annex 3 (see SDK LICENSE) | Semtech, STMicroelectronics |
| ST Utilities | BSD-3-Clause | STMicroelectronics |
| Sidewalk Unified Demo Apps (`apps/common`) | Annex 2 (see SDK LICENSE) | Amazon.com, Inc. or its affiliates |
| Common STM32 Platform Code (`apps/st/common`) | SLA (see SDK LICENSE) | STMicroelectronics |
| Common STM32WBAxx Platform Code (`apps/st/stm32wba`) | SLA (see SDK LICENSE) | STMicroelectronics |
| Sidewalk Sample Apps for WBAxx (`apps/st/stm32wba/sid_xxx`) | SLA + Annex 2 + Annex 3 | STMicroelectronics, Amazon, Semtech |
| Sidewalk PAL: Common STM32 PAL (`pal/st/common`) | SLA (see SDK LICENSE) | STMicroelectronics |
| Sidewalk PAL: STM32WBAxx PAL (`pal/st/stm32wba`) | SLA (see SDK LICENSE) | STMicroelectronics |
| Semtech Common Interfaces / Drivers (`platform/sid_mcu/semtech`) | SLA + Annex 2 + Annex 3 | STMicroelectronics, Amazon, Semtech |
| Spirit2 (S2-LP) Radio Driver | SLA (see SDK LICENSE) | STMicroelectronics |
| STM32WBAxx Sidewalk HAL (`platform/sid_mcu/st/hal/stm32wba`) | SLA (see SDK LICENSE) | STMicroelectronics |
| STM32WLxx Radio App Driver | SLA (see SDK LICENSE) | STMicroelectronics, Semtech |
| Teseo GNSS Receivers Driver | SLA (see SDK LICENSE) | STMicroelectronics |
| Sidewalk MCU SDK Library (prebuilt) | Amazon Sidewalk Content License | Amazon.com, Inc. or its affiliates |
| nanopb (in `sidewalk_sdk_prebuilt`) | Zlib | Petteri Aimonen |
| LK embedded kernel (in `sidewalk_sdk_prebuilt`) | MIT | Travis Geiselbrecht |
| uthash (in `sidewalk_sdk_prebuilt`) | BSD-1-Clause | Troy D. Hanson |
| X-CUBE-MEMS1 BSP + PID drivers (LSM6DSV16X, LIS2DUXS12, LPS22DF, SHT40AD1B, STTS22H, ISM6HG256X, IIS2DULPX, ILPS22QS) | BSD-3-Clause | STMicroelectronics |
| STMems_Machine_Learning_Core (UCF + header for `asset_tracking`) | BSD-3-Clause | STMicroelectronics |
| Sidewalk Provision Tool (`tools/provision` in the SDK) | Apache-2.0 | Amazon.com, Inc. or its affiliates |

### License files included with this repository

* `LICENSE` — MIT license for original Avnet content
* `examples/sidewalk-mems-wba55/firmware/mlc/LICENSE` — BSD-3-Clause for the STMems_Machine_Learning_Core file in that directory

### Where to find the full upstream license texts

* The authoritative per-component license texts (SLA0048, Amazon Annex 2,
  Semtech Annex 3, Annex 1 for lib_gnss) are reproduced in
  `STM32-Sidewalk-SDK/LICENSE.md` in the upstream SDK.
* `sidewalk_sdk_prebuilt/LICENSE.txt` in the upstream SDK contains the full
  Amazon Sidewalk Content License terms.
* `X-CUBE-CRYPTOLIB` (CMOX) license terms are presented as a click-through
  agreement on st.com at the time of download; integrators must accept
  those terms separately and are bound by them when linking CMOX into
  their own firmware.

---

## Acknowledgments

Pre-built firmware images in this repository were produced by compiling the
STM32-Sidewalk-SDK against X-CUBE-MEMS1 BSP drivers, X-CUBE-CRYPTOLIB
(CMOX), and STMems_Machine_Learning_Core UCF configurations. Source code
for those upstream components is available from STMicroelectronics
(st.com / github.com/STMicroelectronics) and Amazon
(github.com/aws). The Avnet /IOTCONNECT additions are limited to the
files identified above as original Avnet content.
