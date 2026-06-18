# STM32 Sidewalk BLE Location Demo (WBA55 + /IOTCONNECT)

A **minimal, sensor-free** example whose only job is to prove **AWS IoT Core
Device Location** works end-to-end for a BLE-only Amazon Sidewalk device, surfaced
through **/IOTCONNECT**. Once location is confirmed here in isolation, the
mechanism is merged into the [MEMS sensor example](../sidewalk-mems-wba55/README.md)
so a single device reports **sensor data *and* location**.

It builds on the stock [`ble-wba55`](../ble-wba55/README.md) / `sid_ble` app and
adds one thing: a **Level-1 BLE gateway-proximity location resolve** via the
Amazon Sidewalk Location Library. No GNSS or Wi-Fi hardware — the WBA55 board on
its own is enough.

---

## How BLE location works here (read this first)

For a BLE-only Sidewalk device, **the device does not compute its position**.
It asks the cloud to resolve it, and AWS returns coordinates based on the
approximate location of the nearby **opted-in Sidewalk gateway** (Community
Finding) the device is connected through. This is the Location Library's
**Level 1 — "Connected to Sidewalk via BLE", "no additional power draw"**.

Two consequences that shape this whole example:

1. **Resolution is coarse and coverage-dependent.** It only works when a
   Community-Finding gateway (Echo 4th-gen, many Ring devices, …) is within BLE
   range. With none nearby, the device reports `LVL1_UNAVAILABLE` and no
   coordinates are ever produced. **Confirm coverage at your bench before
   blaming firmware.**
2. **Location data does *not* flow through a /IOTCONNECT uplink decoder.** AWS
   resolves position server-side and publishes **GeoJSON to a separate "location
   destination"**. Getting that into /IOTCONNECT is a backend wiring step
   (see [§5](#5-aws--iotconnect-data-flow)), not a payload decoder.

> **SDK-version note.** The newer "attach a location-resolve to your own sensor
> uplink" mechanism (`resolve_location` TX attribute, Location Library Guide
> PS 1.0 Rev A §2.7) is **not present** in the location library shipped with
> STM32-Sidewalk-SDK 1.19.4.20 — its `sid_msg_desc_tx_attributes` has no such
> field. This example therefore uses the **dedicated `sid_location_run()`**
> path, which is fully supported and is the right tool for an isolated proof.
> The merge step revisits piggybacking — see [§8](#8-next-step-merge-with-the-mems-example).

---

## Scope: Prototype Flow (Not Mass Production)

Uses the **Amazon Sidewalk prototyping flow** — per-device certificate JSON,
flashed one device at a time, up to 1,000 prototype devices. For production
manufacturing integration, engage **AWS and the /IOTCONNECT team** first. (Same
disclaimer as the other examples in this repo.)

---

## 1) Hardware

| Item | Notes |
|---|---|
| NUCLEO-WBA55CG | Sidewalk host MCU. SWD via on-board ST-LINK. |
| USB micro-B cable | ST-LINK programming + UART log. |
| A Community-Finding Sidewalk gateway in range | **Required for any coordinates to resolve.** Echo (4th-gen+) / supported Ring devices with Amazon Sidewalk + Community Finding enabled. |

No expansion shield. No sub-GHz radio. No GNSS.

## 2) Software / SDK

Same toolchain as the other WBA55 examples (STM32CubeIDE, STM32CubeProgrammer
CLI, Python 3.10+, X-CUBE-CRYPTOLIB/CMOX). SDK at
`<WORKSPACE_ROOT>/STM32-Sidewalk-SDK`.

This example needs the **location-enabled (full) Sidewalk library variant** and
the `SID_SDK_CONFIG_ENABLE_LOCATION=1` flag — both covered in
[`firmware/README.md`](firmware/README.md).

## 3) Firmware

The bespoke source ([`firmware/STM32_WPAN/App/location_wba55.c` / `.h`](firmware/STM32_WPAN/App/))
wraps the Sidewalk Location Library for BLE Level-1 and is driven from the stock
`sid_ble` demo task. Copy it into the SDK and apply the `app_sidewalk.c` hooks
exactly as listed in [`firmware/README.md`](firmware/README.md):

- link `sidewalk_sdk_full_stm32wba_ble.a` (not the basic archive),
- define `SID_SDK_CONFIG_ENABLE_LOCATION=1` and `SID_APP_LOCATION_ENABLED=1`,
- `location_wba55_init()` after `sid_init()`, `location_wba55_run()` in `send_ping()`.

## 4) Generate manufacturing data + flash

Identical to the other examples — create the device in /IOTCONNECT, generate the
WBA55 manufacturing image from its certificate JSON, then erase → flash firmware
→ flash MFG:

```
python3 <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/tools/provision/provision.py \
  st aws --chip WBA55xG \
  --certificate_json <DEVICE_JSON>.json \
  --output_bin mfg_wba55.bin --output_hex mfg_wba55.hex
```

See [sidewalk-mems-wba55 README §5–6](../sidewalk-mems-wba55/README.md) for the
provisioning + `connect-under-reset` flashing details (unchanged here).

## 5) AWS / IOTCONNECT data flow

```
 device  --BLE L1 resolve-->  Sidewalk gateway  -->  AWS IoT Core for Sidewalk
                                                          |
                            (Positioning = Enabled)       v
                                              AWS IoT Core Device Location
                                              resolves BLE gateway proximity
                                                          |
                                                          v
                                          LOCATION DESTINATION (IoT rule)
                                          GeoJSON: {coordinates:[lon,lat,alt],
                                                    properties:{measurementType:"BLE",...}}
                                                          |
                                       (backend-wired forward)   <-- CONFIRM
                                                          v
                                                    /IOTCONNECT
```

What must be true on the cloud side — your backend team reportedly enabled
location services, so this example's job is to **confirm the contract**:

1. **Positioning is Enabled** on the wireless device, with a **location
   destination** set. In a CLI flow this is
   `Positioning=Enabled` + `Sidewalk.Positioning.DestinationName`; through
   /IOTCONNECT it is whatever the backend exposed (a device-profile/template
   setting, or applied automatically at provision time). **→ Confirm how a new
   device gets positioning enabled without CLI access.**
2. **The resolved GeoJSON reaches /IOTCONNECT.** Because location bypasses the
   uplink decoder, the location destination must be forwarded into /IOTCONNECT
   (e.g. a rule/Lambda mapping `coordinates` → device lat/lon attributes).
   **→ Confirm where you will see the coordinate: a /IOTCONNECT map widget,
   lat/lon attributes, or only in the AWS console.**

> No uplink decoder or TLV template is shipped with this example on purpose —
> the dedicated location frames are consumed by AWS Device Location, not decoded
> as application data. A device template is still needed to *create* the device
> in /IOTCONNECT; its location attributes depend on the forward contract in
> step 2, so it is documented rather than guessed. Once the contract is
> confirmed we add the matching template here.

## 6) Verify

**On the device (UART)** — proves the resolve left the device:
```
[INFO]: LOC: location library initialized (BLE gateway, L1)
[INFO]: LOC: Level-1 BLE location resolve requested
[INFO]: LOC: result status=LVL1_READY (BLE gateway location available) ...
[INFO]: LOC: result status=SEND_DONE ...
```
`LVL1_UNAVAILABLE` → no opted-in gateway in BLE range (coverage problem, not a
firmware bug).

**On the cloud** — proves resolution + delivery: a `measurementType:"BLE"`
GeoJSON point appears at the location destination, and (per the confirmed
contract) a coordinate shows in /IOTCONNECT.

## 7) Troubleshooting

| Symptom | Likely cause |
|---|---|
| Linker `undefined reference to sid_location_init` | Still linking the **basic** archive — swap to `sidewalk_sdk_full_stm32wba_ble.a` ([firmware/README.md](firmware/README.md) step 1). |
| Compiles, but `sid_location_run` returns error | `SID_SDK_CONFIG_ENABLE_LOCATION=1` missing, or called before the link is READY/time-synced. |
| `LVL1_UNAVAILABLE` every cycle | No Community-Finding gateway in BLE range, or the gateway hasn't opted in. |
| Device logs `LVL1_READY`/`SEND_DONE` but nothing in /IOTCONNECT | Positioning not enabled on the device, or the location destination isn't forwarded to /IOTCONNECT — **backend contract (§5)**. |

## 8) Next step: merge with the MEMS example

Once location is confirmed here, fold it into
[`sidewalk-mems-wba55`](../sidewalk-mems-wba55/README.md) so one device reports
sensors **and** location. Because this SDK has no `resolve_location` piggyback,
the merge sends **two uplinks from the one device**: the existing sensor TLV via
`sid_put_msg()`, and a Level-1 location resolve via `sid_location_run()`.

**Open risk to verify during the merge:** AWS docs state that enabling
positioning stops the *raw uplink payload* from reaching the uplink destination.
Whether that affects the **application** (sensor) frames — or only the dedicated
location frames — must be tested: enable positioning on the merged device and
confirm the sensor TLV still lands in /IOTCONNECT. If it does, one board carries
both. If it doesn't, sensors and location need separate devices (= separate
boards, since one board is one Sidewalk identity), or an SDK with the
`resolve_location` piggyback.

---

## Confirm with the /IOTCONNECT backend team

1. How is **Positioning enabled** for a Sidewalk device created via /IOTCONNECT
   (no AWS CLI access)? Per-device toggle, device profile, or automatic?
2. What is the **location destination**, and **how is its GeoJSON forwarded into
   /IOTCONNECT**? What device attribute(s) / widget will display the coordinate?
3. Is there a **device template** we should use for a location-only device (with
   lat/lon/accuracy attributes), or does location land outside the template?
