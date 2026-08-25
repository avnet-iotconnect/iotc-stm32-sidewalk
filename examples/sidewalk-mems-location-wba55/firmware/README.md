# sidewalk-mems-location firmware integration

This example ships **no source files of its own** — it composes the two
sibling overlays into one build of the SDK's `sid_ble` app. The canonical
sources stay with their parents:

| Overlay | Canonical source | What it provides |
|---|---|---|
| MEMS sensors + downlink commands | [`../../sidewalk-mems-wba55/firmware/`](../../sidewalk-mems-wba55/firmware/README.md) | `sensors_iks4a1.c/.h`, `sensors_iks5a1.c`, `commands_iks4a1.c/.h`, MLC configs, IKS BSP conf, I²C bus glue, X‑CUBE‑MEMS1 driver instructions |
| BLE L1 location wrapper | [`../../sidewalk-location-wba55/firmware/`](../../sidewalk-location-wba55/firmware/README.md) | `location_wba55.c/.h` |

Apply **both** parents' "copy into the SDK" steps to the same
`apps/st/stm32wba/sid_ble/` checkout. The file sets don't overlap, and every
source guards its body with its own enable flag, so all of them can live in
the SDK tree permanently:

- `sensors_*.c` compile empty unless `SID_APP_IKS4A1_ENABLED=1` /
  `SID_APP_IKS5A1_ENABLED=1`
- `location_wba55.c` compiles empty unless `SID_APP_LOCATION_ENABLED=1`

## `app_sidewalk.c` hooks — both sets coexist

The MEMS hooks are covered by the MEMS firmware README ("what's already wired
up"). The location hooks are the same three from the location example —
verbatim, no merge-specific changes:

**1. Include** (next to the guarded sensor includes):
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
#  include "location_wba55.h"
#endif
```

**2. After `sid_init()` succeeds** (right after
`context->sidewalk_handle = sid_handle;`):
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
    (void)location_wba55_init(sid_handle);
#endif
```

**3. In `send_ping()`, after `app_context->counter++`** — deliberately
**outside** the payload `#if/#elif/#else`, so it runs identically whether the
uplink that just went out was the IKS sensor TLV, the simple-seq frame, or the
stock counter:
```c
#if defined(SID_APP_LOCATION_ENABLED) && (SID_APP_LOCATION_ENABLED == 1)
    (void)location_wba55_run(app_context->sidewalk_handle);
#endif
```

`location_wba55_run()` is internally throttled
(`LOCATION_WBA55_MIN_PERIOD_S`, default 120 s), so calling it on every demo
tick is safe regardless of the sensor uplink interval set via the
`set_interval` downlink command.

## Build-system changes (CubeIDE `.cproject`) — the union

Relative to the stock MEMS build configuration:

1. **Link the full (location-enabled) Sidewalk archive.** Replace every
   `sidewalk_sdk_basic` reference (include path, library search path, and the
   `:sidewalk_sdk_basic_stm32wba_ble_with_logs.a` archive name) with
   `sidewalk_sdk_full`. The basic archive has no `sid_location_*` symbols —
   forgetting this is the classic `undefined reference to sid_location_init`.
2. **Compiler defines** (C compiler → preprocessor), final combined set:
   ```
   SID_APP_IKS4A1_ENABLED=1        (or 0, with IKS5A1=1 — exactly one)
   SID_APP_IKS5A1_ENABLED=0
   SID_SDK_CONFIG_ENABLE_LOCATION=1
   SID_APP_LOCATION_ENABLED=1
   ```
   Do **not** define `SID_SDK_CONFIG_ENABLE_WIFI` / `_GNSS` — BLE-only needs
   no scan PALs.

Or skip the manual work: `LOCATION=1 ./scripts/build-firmware.sh <shield>`
applies the archive swap + defines onto a pristine `.cproject`, builds
headlessly, restores the project file, and drops
`binaries/sid_ble_<board>_<shield>_loc.hex`.

## Effort-mode pairing — do not "fix" one side only

`location_wba55.c` ships with `manage_effort = false` **and**
`mode = SID_LOCATION_EFFORT_L1`. These are a matched pair (bench-validated on
SDK 1.19.4.20):

| `manage_effort` | run `mode` | Result |
|---|---|---|
| `false` | `EFFORT_L1` | ✅ shipped config — pinned L1, `SEND_DONE` |
| `true` | `EFFORT_DEFAULT` | ❌ escalates past L1 when no consent gateway is ready (`Trying next effort mode: 3`) → `-6 NOSUPPORT` on BLE-only builds |
| `false` | `EFFORT_DEFAULT` | ❌ `-11 INVALID_ARGS` — `DEFAULT` is only legal under managed effort |

## Expected UART log (combined build, IKS4A1 variant)

```
[INFO]: LOC: location library initialized (BLE gateway, L1)
[INFO]: Sidewalk registration status: Registered
[INFO]: Updated time: ...
[INFO]: IKS4A1 capability discovery uplink (len=.., attempt=1/6)
...
[INFO]: IKS4A1 action uplink seq=2 gps=... stts22h=.. cC sht40_t=.. cC ...
[INFO]: PB unavailable, trying explicit
[INFO]: LOC: result status=SEND_DONE mode=1 link=1
[INFO]: LOC: Level-1 BLE location resolve requested
```

A single `LOC: sid_location_run failed: -6` with `No valid consent GW` on the
**first** cycle after boot is a known transient — it self-heals on the next
connection. `-6` or `-11` on *every* cycle is a config problem: see the
troubleshooting table in the [example README](../README.md#7-troubleshooting).
