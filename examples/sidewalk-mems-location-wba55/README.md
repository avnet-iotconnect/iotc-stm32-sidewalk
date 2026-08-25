# STM32 Sidewalk MEMS + Location Combined Demo (WBA55 / WBA65 + IKS4A1 / IKS5A1 + AWS Device Location + /IOTCONNECT)

One device, two data products: the **MEMS sensor TLV uplink** from
[`sidewalk-mems-wba55`](../sidewalk-mems-wba55/README.md) **plus** the
**BLE Level‑1 network-location resolve** from
[`sidewalk-location-wba55`](../sidewalk-location-wba55/README.md). This is the
"merge step" that the location example's §8 planned: once location was proven in
isolation, fold it into the sensor demo so a single Sidewalk device reports
**sensor data *and* position**.

This example is a **composition, not a fork** — it adds no new source files.
Both parents' firmware overlays are copied into the same SDK app (`sid_ble`),
their hooks are independently guarded (`SID_APP_IKS4A1_ENABLED` /
`SID_APP_IKS5A1_ENABLED` / `SID_APP_LOCATION_ENABLED`) and compose without
conflict, and the combined build simply enables both flag families and links
the **full** (location-enabled) Sidewalk archive. See
[`firmware/README.md`](firmware/README.md) for the exact union.

---

## How the merge works (read this first)

Because STM32-Sidewalk-SDK 1.19.4.20 ships a location library **without** the
newer "attach a location resolve to your own uplink" piggyback API
(`resolve_location` TX attribute), the merged device sends **two independent
uplinks per demo cycle**:

1. **Sensor TLV** via `sid_put_msg()` — same wire format, decoder, and device
   template as the MEMS example. Nothing changes on the /IOTCONNECT side.
2. **Level‑1 BLE location resolve** via `sid_location_run()` — a dedicated
   Sidewalk location-protocol frame consumed by **AWS IoT Core Device
   Location**, never by the uplink decoder.

On the wire you will see the library log `PB unavailable, trying explicit` —
it probes for the piggyback channel, finds none on this SDK, and falls back to
the dedicated frame. That is **expected**, not an error.

Two consequences carried over from the location example (unchanged here):

- **The device never sees the coordinate.** AWS resolves position server-side
  from the connected gateway's location and publishes GeoJSON to the device's
  **positioning destination**. On-target we verified `result->size == 0` in the
  location callback — no position data ever reaches the firmware, so the MEMS
  **decoder needs no changes** for location.
- **Resolution needs a consenting gateway.** A Community-Finding-enabled,
  known-location Amazon gateway (Echo 4th-gen+/supported Ring) must be in BLE
  range, or resolves complete (`SEND_DONE`) without AWS ever storing a
  position. `SEND_DONE` proves the request left the device — not that a
  coordinate exists. The source of truth is `aws iotwireless
  get-resource-position`.

## Scope: Prototype Flow (Not Mass Production)

Same as both parents — Amazon Sidewalk **prototyping flow**, per-device
certificate JSON, up to 1,000 prototype devices. For production engage **AWS
and the /IOTCONNECT team** first.

---

## 1) Hardware

Everything from [MEMS §1](../sidewalk-mems-wba55/README.md#1-hardware), plus
the location prerequisite:

| Item | Notes |
|---|---|
| NUCLEO‑WBA55CG *or* NUCLEO‑WBA65RI | Sidewalk host MCU (WBA65: mind the I²C pin caveat in the MEMS README). |
| X‑NUCLEO‑IKS4A1 *or* X‑NUCLEO‑IKS5A1 | MEMS shield on the Arduino headers. |
| USB cable | ST‑LINK programming + UART log. |
| **A Community-Finding Sidewalk gateway in BLE range** | **Required for any coordinate to resolve.** Without one, sensors still work; location silently never resolves. |

## 2) One-time SDK setup

Do both parents' firmware setups into the **same** `sid_ble` checkout — they
do not overlap:

1. **MEMS overlay** — BSP/PID drivers from X‑CUBE‑MEMS1, sensor/command
   sources, MLC configs, `app_sidewalk.c` sensor hooks:
   [MEMS firmware README](../sidewalk-mems-wba55/firmware/README.md).
2. **Location overlay** — `location_wba55.c/.h` and the three guarded
   `app_sidewalk.c` location hooks:
   [location firmware README](../sidewalk-location-wba55/firmware/README.md).

`location_wba55.c` compiles to an **empty translation unit** unless
`SID_APP_LOCATION_ENABLED=1` (same pattern as the sensor sources), so both
overlays can live permanently in the SDK tree — sensor-only and stock builds
are unaffected.

## 3) Build the combined firmware

The union of both parents' build-system changes (details and rationale in
[`firmware/README.md`](firmware/README.md)):

| Setting | MEMS example | Location example | **Combined** |
|---|---|---|---|
| Sidewalk archive | basic | **full** | **full** (`sidewalk_sdk_full_stm32wba_ble_with_logs.a`) |
| `SID_APP_IKS4A1_ENABLED` / `IKS5A1` | one = 1 | both = 0 | **one = 1** (pick your shield) |
| `SID_SDK_CONFIG_ENABLE_LOCATION` | — | 1 | **1** |
| `SID_APP_LOCATION_ENABLED` | — | 1 | **1** |

### Headless build (recommended)

`scripts/build-firmware.sh` composes location onto any MEMS variant with
`LOCATION=1`:

```bash
# WBA55 + IKS5A1 + location
LOCATION=1 ./scripts/build-firmware.sh iks5a1

# WBA65 + IKS4A1 + location
BOARD=wba65 LOCATION=1 ./scripts/build-firmware.sh iks4a1
```

Output lands at `binaries/sid_ble_<board>_<shield>_loc.hex`.

## 4) Provision + flash

Identical to [MEMS §5–6](../sidewalk-mems-wba55/README.md#5-generate-manufacturing-data-from-iotconnect-json) —
same prototyping flow, same `provision.py`. Mind the **per-chip mfg address**:

| Chip | `--chip` | mfg flash address |
|---|---|---|
| WBA55CG (1 MB) | `WBA55xG` | `0x080FE000` |
| WBA65RI (2 MB) | `WBA65xI` | `0x081FE000` |

```bash
# example: WBA55 + IKS5A1 + location
STM32_Programmer_CLI -c port=SWD mode=UR -e all
STM32_Programmer_CLI -c port=SWD mode=UR -d binaries/sid_ble_wba55_iks5a1_loc.hex -v
STM32_Programmer_CLI -c port=SWD mode=UR -d binaries/sidewalk-mfg/<device>/mfg.bin 0x080FE000 -v -rst
```

> Flashing tips learned the hard way: close any serial monitor (GtkTerm etc.)
> before flashing — it holds the ST‑LINK and causes `DEV_USB_COMM_ERR` — and
> when several probes are attached, target by serial (`-c port=SWD sn=<SN>`)
> so you don't flash the wrong board.

## 5) Cloud-side wiring

Two independent pipes, both must be configured:

1. **Sensor uplink** → the device's **uplink destination** → /IOTCONNECT with
   the unchanged [MEMS decoder + template](../sidewalk-mems-wba55/README.md#10-iotconnect-decoder).
2. **Location** → enable **Positioning** on the wireless device with a
   **positioning destination** (a separate destination from the uplink one):

```bash
aws iotwireless update-wireless-device --id <WirelessDeviceId> \
  --positioning "Enabled" \
  --sidewalk Positioning={DestinationName="<location-destination>"}
```

The resolved position (GeoJSON, `coordinates` ordered `[lon, lat, alt]`,
`measurementType: "BLE"`) reaches the positioning destination and the stored
resource position — it does **not** appear on the uplink topic unless your
positioning destination's IoT rule republishes to MQTT. Query it directly:

```bash
aws iotwireless get-resource-position --resource-type WirelessDevice \
  --resource-identifier <WirelessDeviceId> /dev/stdout
```

### ⚠ Open risk to verify on your account (from location §8)

AWS docs state that enabling positioning can stop the *raw uplink payload*
from reaching the uplink destination. Whether that affects **application
(sensor) frames** or only the dedicated location frames must be confirmed:
after enabling positioning on the merged device, **check the sensor TLV still
lands in /IOTCONNECT**. If it does — one board carries both (the expected
outcome, since the location frames travel outside the application path). If it
doesn't, split sensors and location across two devices or move to an SDK with
the `resolve_location` piggyback.

## 6) Verify

Expected UART interleaving per demo cycle (real bench capture):

```
[INFO]: LOC: location library initialized (BLE gateway, L1)
[INFO]: Sidewalk registration status: Registered
...
[INFO]: IKS4A1 action uplink seq=3 gps=... stts22h=2412 cC ...   <- sensor TLV
[INFO]: PB unavailable, trying explicit                          <- no piggyback on this SDK (expected)
[INFO]: LOC: result status=SEND_DONE mode=1 link=1               <- location resolve uplinked + acked
[INFO]: LOC: Level-1 BLE location resolve requested
[INFO]: Sent message(type: 2, id: N)
```

Then confirm each pipe: sensor values in /IOTCONNECT (MEMS §7/§13), and a
stored position via `get-resource-position` (§5 above).

## 7) Troubleshooting

MEMS-side issues: see [MEMS §14](../sidewalk-mems-wba55/README.md#14-common-failures-and-fixes).
Location-side, all observed and root-caused on the bench:

| Symptom | Meaning | Action |
|---|---|---|
| `LOC: sid_location_run failed: -6` **once at boot**, with `No valid consent GW` | First resolve fires right after time sync, before a consenting gateway is confirmed (`SID_ERROR_NOSUPPORT`). | None — self-heals; subsequent cycles reach `SEND_DONE`. |
| `-6` on **every** cycle, preceded by `Trying next effort mode: 3` | Managed effort escalating past L1 toward Wi‑Fi/GNSS modes this BLE-only build lacks. | Keep `manage_effort = false` (as shipped in `location_wba55.c`). |
| `LOC: sid_location_run failed: -11` every cycle | `SID_ERROR_INVALID_ARGS`: invalid `manage_effort`/`mode` pairing — `EFFORT_DEFAULT` is only legal with managed effort. | Keep the shipped pairing: `manage_effort = false` **with** `mode = SID_LOCATION_EFFORT_L1`. Change both or neither. |
| `SEND_DONE` on device but `get-resource-position` empty | Resolve left the device but AWS never produced a coordinate — no consenting, known-location gateway in range. Not firmware, not AWS config. | Put the device near a Community-Finding-enabled, addressed Amazon gateway. Consider [`geolocation-lr11xx`](../geolocation-lr11xx/README.md) for gateway-independent Wi‑Fi/GNSS location. |
| Position resolves but nothing on your MQTT `#` subscription | Positioning destination's rule doesn't republish to MQTT. | Add a republish action, or read via `get-resource-position`. |
| `TX_UUID verification failed -37` / `rand_key tx != rx` / disconnects `reason 0x16` | Gateway session churn as the device hops between gateways. | Benign — device recovers; resolves still complete. |
| Linker `undefined reference to sid_location_init` | Still linking the **basic** archive. | Swap to the full archive (§3). |

## 8) Next step

If your product needs position **in the payload** (decoded like any sensor
value) or must work without Sidewalk gateway consent, the geolocation examples
take over from here: [`geolocation-teseo`](../geolocation-teseo/README.md)
(on-device GNSS, position as a TLV tag) and
[`geolocation-lr11xx`](../geolocation-lr11xx/README.md) (Wi‑Fi + GNSS scans,
AWS-native solvers, gateway-independent).
