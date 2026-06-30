# STM32 Sidewalk MEMS Sensor Demo (WBA55 + X-NUCLEO-IKS4A1 / IKS5A1 + /IOTCONNECT)

This guide documents a **BLE‑only Sidewalk demo** that reads an on‑board **X‑NUCLEO‑IKS4A1** *or* **X‑NUCLEO‑IKS5A1** MEMS expansion shield from a **NUCLEO‑WBA55CG** and ships the readings to **/IOTCONNECT** over Amazon Sidewalk Link Type 1 (BLE).

It builds on top of the existing [`ble-wba55`](../ble-wba55/README.md) example: rather than forking a new SDK app, this example **enables build flags** in the existing `sid_ble` app that swap the 1‑byte counter uplink for a packed sensor payload. The same firmware source tree builds for either board — flipping one `.cproject` symbol (`SID_APP_IKS4A1_ENABLED=1` vs `SID_APP_IKS5A1_ENABLED=1`) selects which sensor stack is compiled in. The same `/IOTCONNECT` decoder + template handle both, since the TLV wire format is shared.

What you get end‑to‑end, per board:

**X‑NUCLEO‑IKS4A1**
- LSM6DSV16X — 6‑axis IMU (accel + gyro) **+ native 6D orientation** (face_up / face_down / portrait / landscape)
- LPS22DF — barometric pressure
- SHT40AD1B — humidity + temperature
- STTS22H — temperature
- **LIS2DUXS12 — Qvar (capacitive sensing)** — touch the silver pads on the IKS4A1 edge to swing the `qvar` field

**X‑NUCLEO‑IKS5A1**
- ISM6HG256X — 6‑axis IMU (accel + gyro)
- ILPS22QS — barometric pressure + on‑die temperature (surfaced as `temp_stts22h_c` — same TLV tag for dashboard compatibility)
- **IIS2DULPX — Qvar (capacitive sensing)** — touch the silver pads on the IKS5A1 edge to swing the `qvar` field
- *No SHT40* — `temp_sht40_c` / `humidity_sht40_pct` are empty on IKS5A1 builds
- *6D orientation not yet exposed* — `orientation` reports `unknown`

Both share:
- /IOTCONNECT decoder + device template aligned with the demo payload

---

## Production Support in /IOTCONNECT

Production is supported in customer **/IOTCONNECT** instances. Before production rollout, engage **AWS and the /IOTCONNECT team first** to coordinate Amazon Sidewalk manufacturing‑flow enablement in your AWS account/environment.

## Scope: Prototype Flow (Not Mass Production)

This guide uses the **Amazon Sidewalk prototyping flow**:

- Devices are provisioned with per‑device JSON and flashed individually.
- Intended for development / demo validation.
- **Not** the Sidewalk factory manufacturing flow.

Prototype restrictions:

- Up to **1,000** prototype devices.
- No bulk factory onboarding / import‑task provisioning.

For production manufacturing integration, work with the **/IOTCONNECT team**:

- https://docs.sidewalk.amazon/manufacturing/sidewalk-manufacturing-setup-works.html
- https://docs.sidewalk.amazon/manufacturing/sidewalk-device-lifecycle.html
- https://docs.aws.amazon.com/iot-wireless/latest/developerguide/sidewalk-bulk-provisioning-workflow.html

---

## 1) Hardware

| Item | Notes |
|---|---|
| NUCLEO‑WBA55CG | Sidewalk host MCU. SWD via on‑board ST‑LINK. |
| **One of**: X‑NUCLEO‑IKS4A1 *or* X‑NUCLEO‑IKS5A1 | MEMS expansion shield. Stacks on the Arduino headers of the NUCLEO‑WBA55CG. Pick the firmware variant that matches your board. |
| USB micro‑B cable | ST‑LINK programming + UART log. |

The expansion shield communicates via the Arduino I²C connector (PB6 = SCL, PB7 = SDA → STM32WBA55 I2C1). No jumpers or additional wiring are required for the sensors used in this demo.

> X‑NUCLEO‑IKS4A1 also exposes LIS2MDL (3-axis magnetometer); X‑NUCLEO‑IKS5A1 also exposes IIS2MDC. Both are present on the bus but not sampled here.

### Software

- **STM32CubeIDE** (build)
- **STM32CubeProgrammer CLI** at `<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI`
- **Python 3.10+**
- **X‑CUBE‑MEMS1 ≥ v11.x** — provides the IKS4A1 BSP and PID drivers
- **X‑CUBE‑CRYPTOLIB (CMOX)** — required by Sidewalk SDK (see `ble-wba55` README)

### SDK locations

```
<WORKSPACE_ROOT>/STM32-Sidewalk-SDK
<WORKSPACE_ROOT>/X-CUBE-MEMS1                 # extract here from ST.com
<WORKSPACE_ROOT>/X-CUBE-CRYPTOLIB             # CMOX
```

---

## 2) Add the IKS4A1 BSP and PID drivers (X‑CUBE‑MEMS1)

The Sidewalk SDK does **not** ship MEMS sensor drivers. Copy the following from the X‑CUBE‑MEMS1 release into the Sidewalk SDK so the new sensor module can `#include` them and CubeIDE picks them up via existing source folder linking.

### What to copy

From the X‑CUBE‑MEMS1 release tree (path names may differ slightly between releases):

```
X-CUBE-MEMS1/Drivers/BSP/IKS4A1/iks4a1_motion_sensors.c
X-CUBE-MEMS1/Drivers/BSP/IKS4A1/iks4a1_motion_sensors.h
X-CUBE-MEMS1/Drivers/BSP/IKS4A1/iks4a1_env_sensors.c
X-CUBE-MEMS1/Drivers/BSP/IKS4A1/iks4a1_env_sensors.h
X-CUBE-MEMS1/Drivers/BSP/IKS4A1/iks4a1_conf_template.h    -> rename to iks4a1_conf.h
X-CUBE-MEMS1/Drivers/BSP/IKS4A1/iks4a1_bus.{c,h}          (or the equivalent BSP I2C glue)
X-CUBE-MEMS1/Drivers/BSP/Components/lsm6dsv16x/
X-CUBE-MEMS1/Drivers/BSP/Components/lis2duxs12/         (Qvar capacitive front-end)
X-CUBE-MEMS1/Drivers/BSP/Components/lps22df/
X-CUBE-MEMS1/Drivers/BSP/Components/sht40ad1b/
X-CUBE-MEMS1/Drivers/BSP/Components/stts22h/
X-CUBE-MEMS1/Drivers/BSP/Components/Common/             (shared component headers)
```

### Where to put them

A clean layout that does not pollute the Sidewalk SDK source tree:

```
STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/Drivers/BSP/IKS4A1/...
STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/Drivers/BSP/Components/...
```

### Configure `iks4a1_conf.h`

Open the renamed `iks4a1_conf.h` and enable the **five sensors** used here (set `USE_…` macros to 1 for LSM6DSV16X, LIS2DUXS12, LPS22DF, SHT40AD1B, STTS22H; leave LIS2MDL and LSM6DSO16IS at 0 to keep flash usage down). Confirm the I²C bus mapping macros target **I2C1** on the STM32WBA55.

### Wire up I²C in the HAL config

Edit `STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/Config/stm32wbaxx_hal_conf.h`:

```c
/* uncomment the line below */
#define HAL_I2C_MODULE_ENABLED
```

If `iks4a1_bus.c` does not initialize I2C1 itself, add a small `MX_I2C1_Init()` call from `app_entry.c` (or from `sensors_iks4a1_init()`) configuring PB6/PB7 for I2C1 alternate function and a 100 kHz timing.

---

## 3) Sidewalk app changes

The bespoke firmware for this example is kept in this repo under
[`firmware/`](firmware/) (so the sources live in your repo, not only in the ST
SDK fork). See [`firmware/README.md`](firmware/README.md) for exactly where each
file goes in the SDK and the `app_sidewalk.c` integration hooks.

New files (copy into `sid_ble/STM32_WPAN/App/`):

- `sensors_iks4a1.c` / `.h` — sensor read + sid_demo TLV packing
- `commands_iks4a1.c` / `.h` — downlink opcode dispatch (LED, set-interval)

Plus the BSP glue under `firmware/Drivers/BSP/` (`iks4a1_conf.h`,
`stm32wbaxx_nucleo_bus.c` / `.h`).

Patched file:

- `app_sidewalk.c` — when `SID_APP_IKS4A1_ENABLED == 1`, the demo task replaces the 1‑byte counter uplink with the sid_demo capability/action handshake and a packed sensor payload (61 bytes with all sensors present). The hook blocks are listed in `firmware/README.md`.

---

## 4) Build the IKS4A1 Sidewalk demo (STM32CubeIDE)

> **The project is pre-wired.** The IKS4A1 BSP linked-resource entries, include paths, and the `SID_APP_IKS4A1_ENABLED=1` symbol are already committed to `.project` / `.cproject` for both Nucleo configs (Debug and Release). All you do is import the project and click Build.

### One‑time GUI bring‑up

1. **Launch** STM32CubeIDE 1.18 or newer.
2. **Import project**: `File → Open Projects from File System... → Directory:` and pick:
   ```
   <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55
   ```
   Confirm `sid_ble_wba55` shows up and click *Finish*.
3. **Set the active build configuration** to `Debug_Nucleo-WBA55`: in the Project Explorer, right-click `sid_ble_wba55 → Build Configurations → Set Active → Debug_Nucleo-WBA55`.
4. **Build**: `Project → Build Project` (or click the hammer icon, or `Ctrl+B`).

### Build output

```
<WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_ble_wba55.hex
```

### Headless / CLI build

A headless build works once the project's CubeMX natures have been removed from `.project` (already done in this repo). With CubeIDE 1.18+ installed at `/opt/st/stm32cubeide_1.18.0/` (adjust to your install path):

```
/opt/st/stm32cubeide_1.18.0/headless-build.sh \
  -data /tmp/cubeide-ws \
  -import <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55 \
  -cleanBuild "sid_ble_wba55/Debug_Nucleo-WBA55" \
  -no-indexer
```

Use `-build` (not `-cleanBuild`) for incremental rebuilds. The hex lands in the same `Debug_Nucleo-WBA55/sid_ble_wba55.hex` path as the GUI build.

> If you forget to remove the CubeMX natures (`MCUCubeProjectNature`, `MCUCubeIdeServicesRevAev2ProjectNature`) from `.project`, the headless invocation trips an `IocGeneratorAdapter` NPE — use the GUI build until that's fixed.

### Selecting the board (IKS4A1 vs IKS5A1)

Both variants are built from the same source tree by flipping one pair of `.cproject` symbols.

- **IKS4A1 build** (default): `SID_APP_IKS4A1_ENABLED=1`, `SID_APP_IKS5A1_ENABLED=0`
- **IKS5A1 build**: `SID_APP_IKS4A1_ENABLED=0`, `SID_APP_IKS5A1_ENABLED=1`

The flags are mutually exclusive at link time (the IKS4A1 and IKS5A1 BSP component objects use the same global names). The companion `scripts/build-firmware.sh` in this repo flips the flag automatically and produces both hexes in one invocation. See [Section 4 → Headless / CLI build](#headless--cli-build).

### What's already wired up for you (for transparency)

- `Drivers/BSP/IKS4A1`, `Drivers/BSP/IKS5A1`, and `Drivers/BSP/Components` are linked into the project tree (as virtual folders pointing at `APP_ROOT_DIR/Drivers/BSP/...`).
- The Nucleo-WBA55 bus glue file `Drivers/BSP/STM32WBAxx_Nucleo/stm32wbaxx_nucleo_bus.c` is linked as an individual source.
- Compiler include paths added for `IKS4A1`, `IKS5A1`, `Components/Common`, `Components/{lsm6dsv16x,lps22df,sht40ad1b,stts22h,lis2duxs12,ism6hg256x,iis2dulpx,ilps22qs}`, and `STM32WBAxx_Nucleo` (for the bus glue header).
- Defines `SID_APP_IKS4A1_ENABLED` and `SID_APP_IKS5A1_ENABLED` added to all four Nucleo configs (one set to 1, the other to 0 — flip to switch boards).
- `HAL_I2C_MODULE_ENABLED` un-commented in `Config/stm32wbaxx_hal_conf.h`.
- `iks4a1_conf.h` is in place with only the four sensors we use enabled and I2C macros pointing at `BSP_I2C1_*`.

---

## 5) Generate manufacturing data from /IOTCONNECT JSON

When you create a Sidewalk device in /IOTCONNECT, you receive a JSON certificate file:

```
<DEVICE_JSON>.json
```

Generate the WBA55‑compatible manufacturing image:

```
python3 <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/tools/provision/provision.py \
  st aws \
  --chip WBA55xG \
  --certificate_json <DEVICE_JSON>.json \
  --output_bin mfg_wba55.bin \
  --output_hex mfg_wba55.hex
```

Expected output:

```
Using chip config : (WBA55xG:STM32WBA55xG address: 0x80fe000)
Generated .../mfg_wba55.bin
Generated .../mfg_wba55.hex
```

> Do **not** flash the raw `mfg.bin` from /IOTCONNECT. Always run `provision.py st aws --chip WBA55xG` first.

---

## 6) Flash firmware + manufacturing data

> WBA55 needs **connect-under-reset** (`mode=UR`) and often a one-shot retry, because the prior firmware can be in Stop/Standby and miss the first SWD handshake. The wrapper script below handles both.

### One-shot helper (recommended)

```
tools/flash_wba55.sh \
  <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_ble_wba55.hex \
  <mfg.hex>
```

The script does a chip-erase, then writes the firmware, then writes the MFG hex — each step under `mode=UR` with a one-attempt retry on `DEV_CONNECT_ERR`.

### Manual equivalent

```
STM32_Programmer_CLI -c port=SWD mode=UR -e all
STM32_Programmer_CLI -c port=SWD mode=UR -w <firmware.hex>
STM32_Programmer_CLI -c port=SWD mode=UR -w <mfg.hex>
```

If using `.bin` for the manufacturing image, program at **0x080FE000**:

```
STM32_Programmer_CLI -c port=SWD mode=UR -w mfg_wba55.bin 0x080FE000
```

---

## 7) Verify device logs

Expected after reset:

```
[INFO]: MFG storage: validation passed
[INFO]: IKS4A1: sensors initialized
[INFO]: Sidewalk demo started
[INFO]: Sidewalk registration status: Registered        # or: Not registered -> Sidewalk Device Registration done
[INFO]: Established BLE connection (0x0001) with 46:A7:5B:D1:E4:F5 (RPA addr) ...
[INFO]: Updated time: 1464112804.760711                  # time sync via the gateway
[INFO]: IKS4A1 capability discovery uplink (len=14, attempt=1/6)   # repeats every 5 s; up to 6 attempts
[INFO]: IKS4A1: capability-discovery response received; switching to action notifications
[INFO]: IKS4A1 action uplink seq=0 gps=1464112810 stts22h=2345 cC sht40_t=2350 cC sht40_rh=4250 cRH lps22df=101325 cPa
```

- `IKS4A1: ... init failed` → check the I²C wiring, that the IKS4A1 jumpers are at default, and that `iks4a1_conf.h` enables the four sensors used in this demo.
- If the cloud never sends the `0xE0` capability response, the device transitions to `IKS4A1 action uplink` automatically after `IKS4A1_CAP_ATTEMPTS_MAX` (6) attempts — see the handshake note in Section 8.
- `LittleFS: Corrupted dir pair` on the first boot after a full erase is benign (the filesystem is created on first run).

---

## 8) Payload wire format

The uplink is a **`sid_demo`-style TLV stream** (little‑endian values), so the same payload can be parsed by both:

- the **new** [`sidewalk-mems-tlv.py`](../../decoders/sidewalk-mems-tlv.py) decoder (surfaces every IKS4A1 sensor) — submit this for /IOTCONNECT decoder approval, and
- the **existing approved `STsidewalk2`** decoder (surfaces just the STTS22H temperature via tag `0x06`) — useful for a temporary /IOTCONNECT device while the new decoder is in review.

### Two frame types

The firmware emits two `sid_demo` message types, distinguished by the first byte
(`msg_desc = (status_hdr<<7) | (opc<<5) | (cmd_class<<3) | cmd_id`):

| `msg_desc` | opc | meaning | when |
|---|---|---|---|
| `0x40` | NOTIFY (2) | **capability discovery** (cmd_class=DEMO_APP, cmd_id=CAP) | sent every ~5 s after each connect, until the cloud replies |
| `0x41` | NOTIFY (2) | **action / sensor data** (cmd_class=DEMO_APP, cmd_id=ACTION) | sent at the configured interval once the handshake completes |
| `0xE0` | RESP (3)   | **capability response** (downlink, status header set) | the cloud's reply that flips the device into action mode |

### Frame layout

| ofs | size  | field                                   |
|----:|------:|-----------------------------------------|
|  0  | 1     | `msg_desc` (`0x40` capability / `0x41` action) |
|  1+ | var   | TLV stream                              |

### TLV entry format (sid_demo convention)

```
header (1 byte) : (size_type << 6) | (tag & 0x3F)    size_type 0 -> 1-byte length
length (size_type bytes, little-endian)
value  (length bytes, little-endian for multi-byte ints)
```

### Tags emitted in the action frame (`0x41`)

| Tag    | Name                       | Size | Encoding                | Read by `STsidewalk2`? | Read by `sidewalk-mems-tlv`? |
|--------|----------------------------|------|--------------------------|:------:|:------:|
| `0x06` | TEMPERATURE_SENSOR_DATA    | 2 B  | int16 LE °C (whole)     | ✅ → `Temperature`/`sensor_data` | ignored (precision lives in 0x24) |
| `0x07` | CURRENT_GPS_TIME_IN_SECONDS| 4 B  | uint32 LE seconds       | — | ✅ → `gps_time` |
| `0x0C` | LINK_TYPE                  | 1 B  | uint8 (1 = BLE)         | — | ✅ → `link_type` |
| `0x20` | IKS4A1_VERSION            | 1 B  | uint8                   | — | ✅ → `version` |
| `0x21` | IKS4A1_SEQUENCE           | 1 B  | uint8 wrap              | — | ✅ → `Sequence` |
| `0x22` | IKS4A1_ACCEL              | 6 B  | 3 × int16 LE mg         | — | ✅ → `acc_{x,y,z}_g` |
| `0x23` | IKS4A1_GYRO               | 6 B  | 3 × int16 LE (dps × 10) | — | ✅ → `gyr_{x,y,z}_dps` |
| `0x24` | IKS4A1_TEMP_STTS22H_X100  | 2 B  | int16 LE (°C × 100)     | — | ✅ → `temp_stts22h_c` |
| `0x25` | IKS4A1_TEMP_SHT40_X100    | 2 B  | int16 LE (°C × 100)     | — | ✅ → `temp_sht40_c` |
| `0x26` | IKS4A1_HUMIDITY_X100      | 2 B  | uint16 LE (%RH × 100)   | — | ✅ → `humidity_sht40_pct` |
| `0x27` | IKS4A1_PRESSURE_X100      | 4 B  | uint32 LE (hPa × 100)   | — | ✅ → `pressure_hpa` |
| `0x28` | IKS4A1_ORIENTATION        | 1 B  | uint8 (LSM6DSV16X 6D enum: 0=unknown, 1=landscape_right, 2=landscape_left, 3=portrait_up, 4=portrait_down, 5=face_up, 6=face_down) | — | ✅ → `orientation` (string) |
| `0x29` | IKS4A1_QVAR_RAW           | 2 B  | int16 LE (LIS2DUXS12 Qvar count — capacitive) | — | ✅ → `qvar` |

Tags 0x20–0x29 sit safely above sid_demo's reserved range (0x01–0x13), so any decoder that follows the sid_demo convention will silently skip them (per `_read_tlv` semantics) rather than fail.

> **Capability handshake.** Following Amazon's `sid_app_demo` reference, the
> device first emits `0x40` capability frames; the cloud is supposed to reply
> with `0xE0` to flip the device into action mode. Because a decode-only
> /IOTCONNECT pipeline does not run the sid_demo capability responder, the
> firmware also falls back to action frames after `IKS4A1_CAP_ATTEMPTS_MAX`
> (6) unanswered capability attempts — so sensor data always flows. The
> action-frame interval defaults to **15 s** (`CMD_IKS4A1_INTERVAL_DFLT_S`),
> tuned to fit inside the ~60 s Sidewalk BLE connection window. See
> [`firmware/README.md`](firmware/README.md) for the integration code.

Total action-uplink size with all sensors present: **61 bytes** (`SENSORS_IKS4A1_PAYLOAD_MAX_SIZE` is 64). The capability-discovery frame is **14 bytes**. Sidewalk BLE cloud‑mode supports up to 255 bytes, so both fit with comfortable headroom.

Sensible normal‑office values (for sanity‑checking the decoder): accel ≈ (0, 0, 1000) mg, gyro ≈ (0, 0, 0) dps, temps ≈ 22–25 °C, humidity ≈ 30–60 %RH, pressure ≈ 1000–1015 hPa.

---

## 9) Downlink commands (cloud → device)

Sidewalk passes downlink payloads through `on_sidewalk_msg_received()` as a raw byte buffer — there is no fixed Sidewalk‑level command format. The ST `sid_demo` app routes downlinks via a TLV opcode protocol; this example uses a lightweight version of the same idea (1‑byte opcode + optional big‑endian parameters) implemented in [`commands_iks4a1.c`](firmware/STM32_WPAN/App/commands_iks4a1.c).

### Wire format (firmware side)

| ofs  | size | field      | notes                                          |
|-----:|-----:|------------|------------------------------------------------|
|  0   | 1    | opcode     | see table below                                |
|  1   | *    | parameters | network / big‑endian, opcode‑specific          |

| Opcode | Name           | Params              | Effect                                        |
|-------:|----------------|---------------------|-----------------------------------------------|
| `0x01` | `LED_ON`       | none                | Turn user LED (LED_BLUE) on                   |
| `0x02` | `LED_OFF`      | none                | Turn user LED off                             |
| `0x10` | `SET_INTERVAL` | `uint32` BE seconds | Update uplink period; clamped to [60, 3600] s |

The dispatcher logs every recognized command (`CMD led_on`, `CMD set_interval -> 300 s`, …) and warns with `CMD: unknown opcode 0x..` for anything it cannot decode. `SET_INTERVAL` takes effect on the **next** tick of the demo task.

### /IOTCONNECT command workflow (cloud side)

The standard /IOTCONNECT Sidewalk pattern (matching ST's `WLS0723` and `aws-iot-core-for-amazon-sidewalk-sample-app`) defines commands **inline in the device template** as JSON descriptors, then relies on a downlink translator (a Lambda or equivalent) to convert each descriptor to the bytes the firmware decodes.

The template's `commands` array is already wired up:

```json
"commands": [
  { "name": "LED_ON",       "command": "{ \"command\": \"IKS4A1_LED_ON\" }"  },
  { "name": "LED_OFF",      "command": "{ \"command\": \"IKS4A1_LED_OFF\" }" },
  { "name": "SET_INTERVAL", "command": "{ \"command\": \"IKS4A1_SET_INTERVAL\", \"interval_seconds\": <%PARAM%> }",
    "requiredParam": true }
]
```

> The `<%PARAM%>` placeholder is /IOTCONNECT's substitution for the `parameterValue` field of the send call. If your /IOTCONNECT instance uses a different placeholder syntax (e.g. `${PARAM}`), edit the template before importing.

### Downlink translator: JSON command → wire bytes

The cloud-side translator is the counterpart to the uplink decoder. [`decoders/iks4a1_downlink_translator.py`](../../decoders/iks4a1_downlink_translator.py) is a small, dependency-free Python module exposing two entry points:

| Entry point        | Use case                                                                                          |
|--------------------|---------------------------------------------------------------------------------------------------|
| `encode_command()` | Call in-process from any glue code that owns `iotwireless.send_data_to_wireless_device`.          |
| `lambda_handler()` | Drop into AWS Lambda behind /IOTCONNECT's downlink hook, mirroring the AWS sample's `SidewalkDownlinkLambda`. |

Mapping (matches the firmware `commands_iks4a1.h` opcodes):

| Template JSON command                                                  | Wire bytes (hex)        |
|------------------------------------------------------------------------|-------------------------|
| `{"command":"IKS4A1_LED_ON"}`                                         | `01`                    |
| `{"command":"IKS4A1_LED_OFF"}`                                        | `02`                    |
| `{"command":"IKS4A1_SET_INTERVAL","interval_seconds":300}`            | `10 00 00 01 2C`        |

Quick local check of the translator (also clamps `interval_seconds` to [60, 3600]):

```
python3 decoders/iks4a1_downlink_translator.py
```

### Alternative: register raw hex via the bytesCommand REST API

If you'd rather skip the JSON-and-translator layer and let /IOTCONNECT ship hex bytes directly, the REST API exposes a parallel mechanism (PDF spec, *WirelessDevice* §):

1. `POST /api/v2.1/WirelessDevice/{templateGuid}/bytesCommand` to register each command (body in [`device-templates/sidewalk_iks4a1_bytes_commands.json`](../../device-templates/sidewalk_iks4a1_bytes_commands.json)).
2. `POST /api/v2.1/WirelessDevice/{deviceGuid}/send` with `isBytesCommand: true`, `commandGuid`, and `parameterValue` to invoke.

[`tools/register_iks4a1_commands.py`](../../tools/register_iks4a1_commands.py) automates step 1 (dry-run by default; `--apply` to write):

```
python3 tools/register_iks4a1_commands.py \
  --base-url https://<your-device-svc>.iotconnect.io \
  --template-guid <DEVICE_TEMPLATE_GUID> \
  --token "$IOTC_BEARER"            # then re-run with --apply
```

The script also lists the supported `dtName` values via `GET /device-template/datatype/{templateGuid}?hasBytesSupport=true`, so you can confirm `LONG` / `INTEGER` / etc. before posting.

### Verifying the device-side path with the AWS CLI

To bypass /IOTCONNECT entirely and prove the firmware decodes correctly, ship raw bytes via AWS IoT Wireless directly:

```
# led_on  -> 01
aws iotwireless send-data-to-wireless-device \
  --id <WirelessDeviceId> \
  --transmit-mode 0 \
  --payload-data "AQ==" \
  --wireless-metadata 'Sidewalk={Seq=1}'

# set_interval 300 s -> 10 00 00 01 2C  (BE uint32)
aws iotwireless send-data-to-wireless-device \
  --id <WirelessDeviceId> \
  --transmit-mode 0 \
  --payload-data "EAAAASw=" \
  --wireless-metadata 'Sidewalk={Seq=2}'
```

Expected on the UART log:

```
[INFO]: Received message(type: 0, link_mode: 1, id: 0, size 1)
[INFO]: CMD led_on
[INFO]: Received message(type: 0, link_mode: 1, id: 1, size 5)
[INFO]: CMD set_interval -> 300 s
```

---

## 10) /IOTCONNECT decoder

Submit [`decoders/sidewalk-mems-tlv.py`](../../decoders/sidewalk-mems-tlv.py) for /IOTCONNECT decoder approval (allow ~24 h). It:

- Walks the TLV stream and silently skips unknown tags (matching `sid_demo` semantics).
- Returns scaled SI values (g, dps, °C, %RH, hPa) keyed to the attribute names declared in the device template.
- Uses the /IOTCONNECT‑required signature:

```python
def dict_from_payload(base64_input: str, fport: int = None):
    return {"payload": {...}}
```

Quick local check (builds a synthetic TLV payload, encodes to base64, decodes, prints):

```
python3 decoders/sidewalk-mems-tlv.py
```

Expected output: a JSON dump of the synthetic sample payload (~23 °C, ~42 %RH, ~1013 hPa).

---

## 11) /IOTCONNECT device template

Use [`device-templates/sidewalk_st_WBA55+MEMS_template.JSON`](../../device-templates/sidewalk_st_WBA55+MEMS_template.JSON) when creating the device template. It declares:

- The uplink attributes (decoder output fields with units and aggregation types).
- The three downlink commands (`LED_ON`, `LED_OFF`, `SET_INTERVAL`) as JSON descriptors, matching the standard /IOTCONNECT Sidewalk pattern (cf. ST's `WLS0723`).

The cloud-side downlink translator that converts those JSON descriptors to the wire bytes is in [`decoders/iks4a1_downlink_translator.py`](../../decoders/iks4a1_downlink_translator.py) — see Section 9.

---

## 12) Temporary device — validate today using the already‑approved decoder

While `sidewalk-mems-tlv.py` is in /IOTCONNECT decoder review (~24 h), you can prove the full Sidewalk path end‑to‑end **today** by spinning up a second /IOTCONNECT device against the existing approved `STsidewalk2` decoder. **No firmware changes** — the same image works because tag `0x06` carries an STTS22H whole‑degree temperature in the same TLV stream.

Setup:

1. **Use the existing template** [`device-templates/sidewalk_st_demo_template.json`](../../device-templates/sidewalk_st_demo_template.json) — code `STsidewlk2`, name *Sidewalk ST Demo 2*. It pairs with the already‑approved `STsidewalk2` decoder. Import it into your /IOTCONNECT instance if you don't already have it.
2. **Create a second wireless device** under that template (separate `WirelessDeviceId`, separate certificate JSON). This is the "temporary" device.
3. **Provision and flash** exactly as in sections 5–6, using the new device's certificate JSON to generate `mfg_wba55.hex`. The firmware build is unchanged from section 4.
4. **Confirm uplinks.** On the dashboard you'll see two attributes populated each cycle:

   | Attribute     | Source                                           | Example |
   |---------------|--------------------------------------------------|---------|
   | `sensor_data` | Tag `0x06` raw int16 (whole °C, STTS22H)         | `23`    |
   | `Temperature` | Same tag, surfaced as decimal °C                 | `23.0`  |

   Other template attributes (`gps_time`, `link_type`, `ota_*`, `button_*`, `led_*`, etc.) stay empty — the firmware doesn't emit those tags. That's expected and harmless.

5. **When the new decoder is approved**, attach `sidewalk-mems-tlv.py` to a primary device on the [`sidewalk_st_WBA55+MEMS_template.JSON`](../../device-templates/sidewalk_st_WBA55+MEMS_template.JSON) template and decommission the temporary device. The same firmware image carries over without re‑flashing.

> Why this works: our TLV stream emits tag `0x06` (whole °C) **and** tag `0x24` (°C × 100). `STsidewalk2` knows tag `0x06` and silently skips the IKS4A1‑specific tags 0x20–0x27 (sid_demo's `_read_tlv` advances over unknown tags rather than erroring). Once the new decoder is in place, it ignores tag `0x06` and reads tag `0x24` for higher precision plus all the other sensor tags.

---

## 13) End‑to‑end checklist

1. Stack X‑NUCLEO‑IKS4A1 on the NUCLEO‑WBA55CG.
2. Copy X‑CUBE‑MEMS1 IKS4A1 BSP + PID drivers (LSM6DSV16X, LPS22DF, SHT40AD1B, STTS22H) into the SDK.
3. Enable `HAL_I2C_MODULE_ENABLED` in the SDK HAL config.
4. Define `SID_APP_IKS4A1_ENABLED=1` and add include + source paths in CubeIDE.
5. Build `sid_ble` Debug_Nucleo-WBA55.
6. Generate `mfg_wba55.hex` from the /IOTCONNECT JSON.
7. Erase → flash firmware → flash MFG.
8. Confirm `IKS4A1: sensors initialized` and `IKS4A1 uplink seq=...` in the UART log.
9. Apply `sidewalk-mems-tlv.py` decoder + `sidewalk_st_WBA55+MEMS_template.JSON` template in /IOTCONNECT.
10. Wire `decoders/iks4a1_downlink_translator.py` into your /IOTCONNECT downlink hook (or as a Lambda) so dashboard commands hit the firmware as opcode bytes. (Or use the `bytesCommand` REST path with `tools/register_iks4a1_commands.py --apply`.)
11. (Optional) Fire `aws iotwireless send-data-to-wireless-device --payload-data AQ==` to confirm `CMD led_on` lands.

---

## 14) Common failures and fixes

### `cmox_init.h` missing
CMOX library not installed in SDK. Copy `include/` and `lib/` from X‑CUBE‑CRYPTOLIB. See `examples/ble-wba55/README.md`.

### `iks4a1_motion_sensors.h: No such file or directory` (or `iks5a1_motion_sensors.h: …`)
Include path or source folder for the corresponding X‑CUBE‑MEMS1 BSP is missing. Re‑check Step 2 and Step 4.

### `MFG storage: validation failed`
Wrong manufacturing image or wrong address. Re‑generate with `provision.py st aws --chip WBA55xG` and re‑flash.

### `IKS4A1: LSM6DSV16X init failed (-1)` / `IKS5A1: ISM6HG256X init failed (-1)`
The IMU on the expansion shield isn't responding on I²C. Confirm:
- The expansion shield is fully seated on the Arduino headers (most common cause — reseat firmly in both directions).
- You're running the firmware variant that matches the physical board (IKS4A1 firmware on IKS4A1, IKS5A1 firmware on IKS5A1).
- `HAL_I2C_MODULE_ENABLED` is defined in `Config/stm32wbaxx_hal_conf.h`.
- I2C1 (PB6/PB7) is initialized at 100 kHz before `sensors_iks4a1_init()` runs.
- IKS4A1/IKS5A1 jumpers are at factory defaults.

The firmware logs the init failure but **does not** hard-fault on subsequent reads — direct-register paths (6D orientation, Qvar) are guarded by runtime `s_lsm6dsv16x_ok` / `s_lis2duxs12_ok` / `s_iis2dulpx_ok` flags so a `NULL` BSP component handle never gets dereferenced.

### Uplink shows zeros
At least one sensor read returned an error. The module logs a `WARNING` per failing sensor but still sends the rest — check the UART log for the offending sensor and re‑check its driver / power.

### `LittleFS: Corrupted dir pair`
Do a **full erase** before flashing firmware + MFG.

### `CMD: unknown opcode 0x..`
The downlink reached the device but the first byte didn't match a supported opcode. Likely causes:
- The /IOTCONNECT bytes command was registered with the wrong `command` hex (e.g. `0x10` typed as decimal `10`).
- An attribute‑style command was sent instead of `isBytesCommand: true` — check the `POST /WirelessDevice/{deviceGuid}/send` body.
- The `dtName` chosen for `set_interval` does not match what your /IOTCONNECT instance expects (`LONG` vs `INTEGER` vs `INT`). Re‑run `tools/register_iks4a1_commands.py` without `--apply` to print the supported list and adjust the JSON.

### `CMD set_interval -> 60 s` regardless of the value sent
/IOTCONNECT serialized the parameter in **little‑endian** rather than the big‑endian the firmware expects, so the upper 16 bits decode to a huge number and get clamped down to the floor. Either change the `dtName` (some types are LE on this platform) or swap the byte order in `cmd_set_interval()` in `commands_iks4a1.c`.

---

## 15) BLE‑only notes

`sid_ble` uses **Link Type 1 (BLE)** only. The 54‑byte payload fits comfortably inside the BLE cloud‑mode MTU; **do not** widen it without checking the Sidewalk BLE payload limits and the link mode in use.

For full Sidewalk (BLE + Sub‑GHz), the same `sensors_iks4a1.{c,h}` module can be re‑used by `sid_demo`, but the payload may need to be split or shrunk to fit FSK/LoRa Link Type 2/3 MTUs.

---

## Next Step for Production

- [ ] Engage the **/IOTCONNECT team** to integrate the **Amazon Sidewalk** manufacturing flow into your AWS account/environment before production rollout.
