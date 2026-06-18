# sidewalk-location-wba55 firmware sources

Bespoke firmware for the **BLE-only Sidewalk location** proof. Like the MEMS
example, these files are **copied into a checkout of the STM32-Sidewalk-SDK**
(they are not part of the upstream SDK) and `app_sidewalk.c` is patched with the
guarded hooks below. Everything else (Sidewalk stack, FreeRTOS, WBA55 HAL, CMOX)
comes from the SDK.

Base app: **`apps/st/stm32wba/sid_ble`** (the stock 1-byte counter BLE app). We
add a Level-1 BLE gateway-location resolve to its existing demo task.

## Files and where they go

| This folder | Copy to (under `sid_ble/`) | What it is |
|---|---|---|
| `STM32_WPAN/App/location_wba55.c` / `.h` | `STM32_WPAN/App/` | Sidewalk Location Library wrapper (BLE L1) |

## Build-system changes (CubeIDE project, `STM32CubeIDE/STM32WBA55/`)

The location library ships **only in the "full" prebuilt variant** — the basic
archive `sid_ble` links by default omits it. Two changes:

1. **Link the location-enabled archive.** In the linker settings / `.cproject`,
   replace the Sidewalk archive with:
   ```
   sidewalk_sdk_prebuilt/stm32wba/sidewalk_sdk_full/lib/sidewalk_sdk_full_stm32wba_ble.a
   ```
   and point the library search path at that folder. *(Step 1: confirm which
   `.a` the project currently references — grep the `.cproject` for
   `sidewalk_sdk_basic` and swap the `_basic_` segment to `_full_`.)*
2. **Enable the feature flag** in the compiler defines:
   ```
   SID_SDK_CONFIG_ENABLE_LOCATION=1
   ```
   Do **not** define `SID_SDK_CONFIG_ENABLE_WIFI` / `_GNSS` — BLE-only needs no
   scan PALs, and leaving them off keeps flash down.
3. Add the include path for `sid_location.h` (it lives alongside the other
   Sidewalk headers in the full variant's `include/`). Add
   `STM32_WPAN/App/location_wba55.c` to the project sources.

> The header `sid_location.h` is present in the include tree, but the symbols
> (`sid_location_init/_run/_deinit`) resolve **only** against the full archive.
> If you forget step 1 you'll get linker `undefined reference` errors despite a
> clean compile.

## Integration into `app_sidewalk.c`

Guard every hook with `SID_APP_LOCATION_ENABLED` so the stock build is
unaffected (mirrors the MEMS example's `SID_APP_IKS4A1_ENABLED` pattern).

**1. Include** (with the other app includes):
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
#  include "location_wba55.h"
#endif
```

**2. After `sid_init()` succeeds** (near line 437, right after the handle is
valid and before/after `sid_start()`):
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
    (void)location_wba55_init(sid_handle);
#endif
```

**3. In `send_ping()`** — alongside (or instead of) the counter uplink, request
a Level-1 BLE location resolve. It is internally throttled, so calling it on
every demo tick is fine:
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
    (void)location_wba55_run(app_context->sidewalk_handle);
#endif
```
> For the **pure location proof** you can leave the counter `sid_put_msg()` in
> place (harmless) or `#if`-out everything below `SID_PAL_LOG_INFO("Sending
> counter ...")`. Keeping it is useful: it confirms the link is alive even
> before any gateway resolves location.

**4. (Optional) Before `sid_deinit()`** on shutdown/factory-reset paths:
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
    (void)location_wba55_deinit(app_context->sidewalk_handle);
#endif
```

## Runtime prerequisites

- **Time-synced BLE connection.** Level-1 status is documented as "to be used
  with timesync connections". The demo task only sends once the link is READY
  (and the log shows `Updated time: ...`), so triggering the resolve from
  `send_ping()` satisfies this.
- **An opted-in gateway in BLE range.** A Sidewalk gateway (e.g. Echo / many
  Ring devices) with **Community Finding** enabled must be reachable, or the
  callback reports `LVL1_UNAVAILABLE` and no coordinates are ever resolved.

## Expected UART log

```
[INFO]: Sidewalk registration status: Registered
[INFO]: Updated time: 1464112804.760711
[INFO]: LOC: location library initialized (BLE gateway, L1)
[INFO]: LOC: Level-1 BLE location resolve requested
[INFO]: LOC: result status=LVL1_READY (BLE gateway location available) mode=1 link=1
[INFO]: LOC: result status=SEND_DONE mode=1 link=1
```
`LVL1_UNAVAILABLE` instead of `LVL1_READY` → no Community-Finding gateway is in
range; move closer to one or confirm the gateway opted in.
