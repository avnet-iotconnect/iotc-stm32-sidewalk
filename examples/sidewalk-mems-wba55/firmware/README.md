# IKS4A1 firmware sources

These are the **bespoke** firmware files for the WBA55 / WBA65 + X-NUCLEO-IKS4A1
Sidewalk example. They are not part of the upstream STM32 Sidewalk SDK — copy them
into a checkout of the SDK and apply the integration hooks below to reproduce the
build. The same overlay sources build for **both** the NUCLEO-WBA55CG and the
NUCLEO-WBA65RI; the board is selected by the SDK project's board compile macro
(`NUCLEO_WBA55_BOARD` vs `NUCLEO_WBA65_BOARD`), which drives the board-conditional
blocks noted below.

Everything else the build needs (the Sidewalk stack, FreeRTOS, the WBA55/WBA65 HAL,
CMOX) comes from the SDK, and the MEMS sensor drivers come from ST's
**X-CUBE-MEMS1** package (see the parent example README, Section 2).

## Files and where they go in the SDK

The folder layout here mirrors the SDK so you can copy paths verbatim. Root is
`STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/`.

| This folder | Copy to (under `sid_ble/`) | What it is |
|---|---|---|
| `STM32_WPAN/App/sensors_iks4a1.c` / `.h` | `STM32_WPAN/App/` | Sensor read + sid_demo TLV packing (action + capability frames). Loads the LSM6DSV16X asset-tracking MLC at init and emits its `MLC1_SRC` label (tags `0x2A`/`0x2B`). |
| `STM32_WPAN/App/sensors_iks5a1.c` | `STM32_WPAN/App/` | IKS5A1 implementation of the same abstraction (`SID_APP_IKS5A1_ENABLED=1`). Loads the ISM6HG256X asset-tracking MLC at init — same classes/model id as the IKS4A1 build. |
| `STM32_WPAN/App/commands_iks4a1.c` / `.h` | `STM32_WPAN/App/` | Downlink opcode dispatch (LED on/off, set-interval). The `LED_BLUE` board guards accept **both** boards: `#if defined(NUCLEO_WBA55_BOARD) || defined(NUCLEO_WBA65_BOARD)`. |
| `mlc/lsm6dsv16x_asset_tracking.h` | `STM32_WPAN/App/` | Smart Asset Tracking MLC config for LSM6DSV16X (IKS4A1 build) — see [`mlc/README.md`](mlc/README.md) |
| `mlc/ism6hg256x_asset_tracking.h` | `STM32_WPAN/App/` | Smart Asset Tracking MLC config for ISM6HG256X (IKS5A1 build) — same algorithm/classes, from ST's `st-mems-machine-learning-core` repo |
| `Drivers/BSP/IKS4A1/iks4a1_conf.h` | `Drivers/BSP/IKS4A1/` | BSP config — enables LSM6DSV16X, LIS2DUXS12, LPS22DF, SHT40AD1B, STTS22H; I²C macros → `BSP_I2C1_*` |
| `Drivers/BSP/IKS5A1/iks5a1_conf.h` | `Drivers/BSP/IKS5A1/` | BSP config — enables ISM6HG256X, IIS2DULPX, ILPS22QS |
| `Drivers/BSP/STM32WBAxx_Nucleo/stm32wbaxx_nucleo_bus.c` / `.h` | `Drivers/BSP/STM32WBAxx_Nucleo/` | I2C1 bus glue the BSP calls. The `.h` picks the SDA/SCL pin macros by board: `#if defined(NUCLEO_WBA65_BOARD)` (WBA65) `#else` WBA55 default. WBA55 = PB1=SDA/PB2=SCL AF4 I2C1, 100 kHz. **The WBA65 branch currently defaults to the same PB1/PB2/AF4/I2C1 values and is marked `>>> VERIFY` — those pins are NOT yet confirmed against the NUCLEO-WBA65RI schematic (larger package; the GPIO behind Arduino D14/D15 can differ). Confirm before trusting WBA65 sensor data.** |

> Not included (ST-owned): the X-CUBE-MEMS1 PID component drivers
> (`Drivers/BSP/Components/{lsm6dsv16x,lis2duxs12,lps22df,sht40ad1b,stts22h,Common}`).
> Copy those from your X-CUBE-MEMS1 release as described in the parent README.
> The LIS2DUXS12 driver provides the Qvar capacitive front-end used for the
> `qvar` field; the LSM6DSV16X driver provides the native 6D orientation
> engine used for the `orientation` field. Both are enabled via the existing
> BSP wrappers (`IKS4A1_MOTION_SENSOR_Enable_6D_Orientation`,
> `IKS4A1_MOTION_SENSOR_Read_Register` for direct Qvar register access).
> The asset-tracking MLC (tags `0x2A`/`0x2B`) additionally loads the matching
> UCF header from [`mlc/`](mlc/) — LSM6DSV16X on IKS4A1, ISM6HG256X on IKS5A1;
> both emit the same class values so the decoder model is shared.

## Integration into `app_sidewalk.c`

`app_sidewalk.c` is an SDK file, so it is not duplicated here. Apply these hooks,
each guarded by `SID_APP_IKS4A1_ENABLED` so the stock build is unaffected.

**1. Includes** (with the other app includes):

```c
#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
#  include "sensors_iks4a1.h"
#  include "commands_iks4a1.h"
#endif
```

**2. Capability-handshake state** (file scope):

```c
/* Cleared on link teardown so each new session re-runs the sid_demo
 * capability handshake, like the Nordic reference firmware. */
static volatile bool s_iks_cap_response_received = false;

/* Max capability-discovery attempts before falling back to action frames
 * even without a 0xE0 response. Keeps decode-only backends (those that
 * don't run the sid_demo capability responder) from getting stuck in the
 * handshake forever. */
#define IKS4A1_CAP_ATTEMPTS_MAX  6u
static uint8_t s_iks_cap_attempts = 0u;
```

**3. In `on_sidewalk_msg_received()`** — detect the cloud's `0xE0` capability
response and route every downlink to the command dispatcher:

```c
#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
    if ((msg->size >= 1u) &&
        (((const uint8_t *)msg->data)[0] == SENSORS_IKS4A1_MSG_DESC_RESP_CAP)) {
        if (!s_iks_cap_response_received) {
            SID_PAL_LOG_INFO("IKS4A1: capability-discovery response received; "
                             "switching to action notifications");
        }
        s_iks_cap_response_received = true;
    }
    (void)commands_iks4a1_dispatch((const uint8_t *)msg->data, (size_t)msg->size);
#endif
```

**4. In `on_sidewalk_status_changed()`** — reset the handshake on link loss
(`SID_STATE_NOT_READY` path):

```c
#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
    s_iks_cap_response_received = false;   /* re-do capability handshake */
    s_iks_cap_attempts = 0u;
#endif
```

**5. In `send_ping()`** — emit a capability frame until acknowledged *or*
`IKS4A1_CAP_ATTEMPTS_MAX` attempts are spent, then a packed sensor (action)
frame. Replaces the stock 1-byte counter uplink:

```c
#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
    static uint8_t iks_payload[SENSORS_IKS4A1_PAYLOAD_MAX_SIZE];
    uint32_t payload_len;
    const bool in_cap_phase = !s_iks_cap_response_received &&
                              (s_iks_cap_attempts < IKS4A1_CAP_ATTEMPTS_MAX);
    if (in_cap_phase) {
        payload_len = sensors_iks4a1_pack_capability(iks_payload, sizeof(iks_payload));
        s_iks_cap_attempts++;
        SID_PAL_LOG_INFO("IKS4A1 capability discovery uplink (len=%lu, attempt=%u/%u)",
                         (unsigned long)payload_len,
                         (unsigned)s_iks_cap_attempts,
                         (unsigned)IKS4A1_CAP_ATTEMPTS_MAX);
    } else {
        sensors_iks4a1_reading_t reading;
        (void)sensors_iks4a1_read(&reading);
        struct sid_timespec curr_time = {0};
        (void)sid_get_time(app_context->sidewalk_handle, SID_GET_GPS_TIME, &curr_time);
        payload_len = sensors_iks4a1_pack(iks_payload, sizeof(iks_payload),
                                          app_context->counter,
                                          (uint32_t)curr_time.tv_sec, &reading);
    }
    struct sid_msg msg = {.data = iks_payload, .size = payload_len};
#endif
```

**6. In the demo task loop** — 5 s cadence while handshaking, configured
interval afterwards:

```c
#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
    const bool in_cap_phase = !s_iks_cap_response_received &&
                              (s_iks_cap_attempts < IKS4A1_CAP_ATTEMPTS_MAX);
    const uint32_t interval_ms = in_cap_phase ? 5000u : commands_iks4a1_get_interval_ms();
    osDelay(interval_ms);
#endif
```

> **Capability handshake — operational note.** The device sends up to
> `IKS4A1_CAP_ATTEMPTS_MAX` (6) capability-discovery frames at 5 s intervals,
> then proceeds to action frames whether or not the cloud has replied with
> `0xE0`. A sid_demo cloud sample app will respond and the device transitions
> earlier; a decode-only /IOTCONNECT pipeline never sends `0xE0` and the
> device transitions on the fallback. The default action interval
> (`CMD_IKS4A1_INTERVAL_DFLT_S = 15 s`) is tuned for Sidewalk BLE: the Echo
> tears the link down ~60 s after each connect, so action frames need to fire
> inside that window. Adjust via the `SET_INTERVAL` downlink command if your
> use case allows longer intervals.

`init` is wired in `sensors_iks4a1_init()` (called once at app start, after
`BSP_I2C1_Init()`), invoked from the app's bring-up alongside the other init.

## Build-system changes (CubeIDE project)

These changes are **already committed to the STM32WBA55 project** (`STM32CubeIDE/STM32WBA55/`, both `Debug_Nucleo-WBA55` and `Release_Nucleo-WBA55` configs). To also build for the NUCLEO-WBA65RI, apply the **same** changes to the stock SDK **STM32WBA65** project (`STM32CubeIDE/STM32WBA65/`, its `Debug_Nucleo-WBA65` / `Release_Nucleo-WBA65` configs) — the stock WBA65 `sid_ble` project does **not** ship the MEMS wiring. The SDK already provides the WBA65 CubeIDE project itself (project/hex `sid_ble_wba65`, configs `Debug_Nucleo-WBA65` / `Release_Nucleo-WBA65`, board macro `NUCLEO_WBA65_BOARD`); no new SDK project needs to be created.

In `STM32CubeIDE/STM32WBA55/` (and, for WBA65, `STM32CubeIDE/STM32WBA65/`):

- **`.cproject`** — define `SID_APP_IKS4A1_ENABLED=1`; add include paths for
  `Drivers/BSP/IKS4A1`, `Drivers/BSP/Components/Common`,
  `Drivers/BSP/Components/{lsm6dsv16x,lps22df,sht40ad1b,stts22h}`, and
  `Drivers/BSP/STM32WBAxx_Nucleo`.
- **`.project`** — link `Drivers/BSP/IKS4A1`, `Drivers/BSP/Components`, and the
  `stm32wbaxx_nucleo_bus.c` source into the project tree.
- **`Config/stm32wbaxx_hal_conf.h`** — uncomment `#define HAL_I2C_MODULE_ENABLED`.

See the parent [example README](../README.md), Sections 2–4, for the full
step-by-step (including the per-board project/build-config/hex names and the
WBA65 I²C pin-verification caveat).
