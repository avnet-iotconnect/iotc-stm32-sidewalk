# IKS4A1 firmware sources

These are the **bespoke** firmware files for the WBA55 + X-NUCLEO-IKS4A1 Sidewalk
example. They are not part of the upstream STM32 Sidewalk SDK — copy them into a
checkout of the SDK and apply the integration hooks below to reproduce the build.

Everything else the build needs (the Sidewalk stack, FreeRTOS, the WBA55 HAL,
CMOX) comes from the SDK, and the MEMS sensor drivers come from ST's
**X-CUBE-MEMS1** package (see the parent example README, Section 2).

## Files and where they go in the SDK

The folder layout here mirrors the SDK so you can copy paths verbatim. Root is
`STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/`.

| This folder | Copy to (under `sid_ble/`) | What it is |
|---|---|---|
| `STM32_WPAN/App/sensors_iks4a1.c` / `.h` | `STM32_WPAN/App/` | Sensor read + sid_demo TLV packing (action + capability frames) |
| `STM32_WPAN/App/commands_iks4a1.c` / `.h` | `STM32_WPAN/App/` | Downlink opcode dispatch (LED on/off, set-interval) |
| `Drivers/BSP/IKS4A1/iks4a1_conf.h` | `Drivers/BSP/IKS4A1/` | BSP config — enables only LSM6DSV16X, LPS22DF, SHT40AD1B, STTS22H; I²C macros → `BSP_I2C1_*` |
| `Drivers/BSP/STM32WBAxx_Nucleo/stm32wbaxx_nucleo_bus.c` / `.h` | `Drivers/BSP/STM32WBAxx_Nucleo/` | I2C1 bus glue (PB1=SDA/PB2=SCL AF4, 100 kHz) the BSP calls |

> Not included (ST-owned): the X-CUBE-MEMS1 PID component drivers
> (`Drivers/BSP/Components/{lsm6dsv16x,lps22df,sht40ad1b,stts22h,Common}`).
> Copy those from your X-CUBE-MEMS1 release as described in the parent README.

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
#endif
```

**5. In `send_ping()`** — emit a capability frame until acknowledged, then a
packed sensor (action) frame. Replaces the stock 1-byte counter uplink:

```c
#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
    static uint8_t iks_payload[SENSORS_IKS4A1_PAYLOAD_MAX_SIZE];
    uint32_t payload_len;
    if (!s_iks_cap_response_received) {
        payload_len = sensors_iks4a1_pack_capability(iks_payload, sizeof(iks_payload));
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
    const uint32_t interval_ms = s_iks_cap_response_received
                               ? commands_iks4a1_get_interval_ms()
                               : 5000u;
    osDelay(interval_ms);
#endif
```

> **Capability handshake — operational note.** As written, the device keeps
> sending capability-discovery frames until the cloud replies with `0xE0`
> (this mirrors Amazon's `sid_app_demo` reference). A backend that does not run
> the sid_demo capability responder (e.g. a plain decode-only /IOTCONNECT
> pipeline) never sends `0xE0`, so the device stays in capability discovery and
> never emits sensor data. If your backend doesn't respond, change `send_ping()`
> to fall back to action frames after a few unanswered attempts (or unconditionally).

`init` is wired in `sensors_iks4a1_init()` (called once at app start, after
`BSP_I2C1_Init()`), invoked from the app's bring-up alongside the other init.

## Build-system changes (CubeIDE project)

In `STM32CubeIDE/STM32WBA55/`:

- **`.cproject`** — define `SID_APP_IKS4A1_ENABLED=1`; add include paths for
  `Drivers/BSP/IKS4A1`, `Drivers/BSP/Components/Common`,
  `Drivers/BSP/Components/{lsm6dsv16x,lps22df,sht40ad1b,stts22h}`, and
  `Drivers/BSP/STM32WBAxx_Nucleo`.
- **`.project`** — link `Drivers/BSP/IKS4A1`, `Drivers/BSP/Components`, and the
  `stm32wbaxx_nucleo_bus.c` source into the project tree.
- **`Config/stm32wbaxx_hal_conf.h`** — uncomment `#define HAL_I2C_MODULE_ENABLED`.

See the parent [example README](../README.md), Sections 2–4, for the full
step-by-step.
