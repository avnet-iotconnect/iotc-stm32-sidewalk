# STM32 Sidewalk BLE Demo (WBA55 + IOTCONNECT)

This guide documents a **BLE‑only Sidewalk demo** on **Nucleo‑WBA55** using **ST’s STM32‑Sidewalk‑SDK** and **IOTCONNECT**. It includes:

- Manufacturing data generation from IOTCONNECT JSON
- STM32CubeIDE build steps for `sid_ble`
- Flashing firmware + manufacturing data
- IOTCONNECT decoder + device template aligned with the demo payload

Everything below assumes you have cloned **STM32‑Sidewalk‑SDK**. If your paths differ, adjust accordingly.

---

## Images

![NUCLEO‑WBA55 (example)](https://commons.wikimedia.org/wiki/Special:FilePath/Nucleo-board.jpg)

---

## 1) Prerequisites

### Hardware
- NUCLEO‑WBA55CG board
- SWD connection via onboard ST‑LINK (default on Nucleo)

### Software
- STM32CubeIDE (for building)
- STM32CubeProgrammer CLI
  - Installed at: `<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI`
- Python 3.10+ (already present in this environment)

### SDK location
- **STM32‑Sidewalk‑SDK** at:
  - `<WORKSPACE_ROOT>/STM32-Sidewalk-SDK`
## 2) Add required cryptographic middleware (CMOX)

STM32‑Sidewalk‑SDK requires **X‑CUBE‑CRYPTOLIB (CMOX)** headers and libs.

You must copy the `include/` and `lib/` folders into:

```
STM32-Sidewalk-SDK/platform/sid_mcu/st/stm32common/Middlewares/ST/STM32_Cryptographic/
```

Expected layout:
```
.../STM32_Cryptographic/include/cmox_init.h
.../STM32_Cryptographic/include/cmox_crypto.h
.../STM32_Cryptographic/lib/libSTM32Cryptographic_CM33.a
```

If these files are missing, the build fails with `cmox_init.h`/`cmox_crypto.h` errors.

---

## 3) Build the BLE‑only Sidewalk demo (STM32CubeIDE)

This repo uses **BLE‑only** (`sid_ble`) on WBA55.

### Project location
```
STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55
```

### CubeIDE import
1. `File > Import...`
2. `General > Existing Projects into Workspace`
3. Root directory:
   ```
   <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55
   ```
4. Build `Debug_Nucleo-WBA55`

### Build output (firmware)
```
<WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_ble_wba55.hex
```

---

## 4) Generate manufacturing data from IOTCONNECT JSON

When you create a Sidewalk device in IOTCONNECT, you receive a JSON file such as:

```
<DEVICE_JSON>.json
```

Use ST’s provisioning tool in the SDK to generate a **WBA55‑compatible** manufacturing image:

```
python3 <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/tools/provision/provision.py \
  st aws \
  --chip WBA55xG \
  --certificate_json <DEVICE_JSON>.json \
  --output_bin mfg_wba55.bin \
  --output_hex mfg_wba55.hex
```

You should see:
```
Using chip config : (WBA55xG:STM32WBA55xG address: 0x80fe000)
Generated .../mfg_wba55.bin
Generated .../mfg_wba55.hex
```

**Important:** Do **not** use the raw `mfg.bin` from IOTCONNECT directly.  
You must generate the WBA55‑specific MFG image as above.

---

## 5) Flash firmware + manufacturing data

### Full erase (clears LittleFS and old MFG)
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -e all
```

### Flash firmware
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -w \
<WORKSPACE_ROOT>/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55/sid_ble_wba55.hex
```

### Flash manufacturing data
Preferred:
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -w mfg_wba55.hex
```

If using `.bin`, program at **0x080FE000**:
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -w mfg_wba55.bin 0x080FE000
```

---

## 6) Verify device logs

Expected when MFG is correct:
```
[INFO]: MFG storage: validation passed
[INFO]: Sidewalk demo started
[INFO]: Sidewalk Device Registration done
```

If you see:
```
[ERROR]: MFG storage: validation failed
```
then the manufacturing image is wrong or flashed to the wrong address.

If you see:
```
[ERROR]: LittleFS: Corrupted dir pair
```
do a **full erase** and re‑flash firmware + MFG.

---

## 7) IOTCONNECT decoder (payload parsing)

Decoder file:
Use the decoder file provided with your IOTCONNECT integration (this repo includes an example at `decoders/stsidewalk.py`).

The decoder:
- Parses the Sidewalk **demo TLV payload**
- Outputs the fields expected by the device template
- Uses the IOTCONNECT required signature:

```python
def dict_from_payload(base64_input: str, fport: int = None):
    return {"payload": {...}}
```

---

## 8) /IOTCONNECT device template

Use a device template aligned with the demo payload + decoder (this repo includes an example at `device-templates/sidewalk_st_demo_template.json`).

It includes:
- `sensor_data`, `Temperature`
- `gps_time`, `link_type`
- button/LED metadata and actions
- OTA fields (optional, reported by demo)

---

## 9) End‑to‑end checklist

1. Build `sid_ble` in CubeIDE.
2. Generate `mfg_wba55.hex` from IOTCONNECT JSON.
3. Erase → flash firmware → flash MFG.
4. Confirm `MFG storage: validation passed`.
5. Use decoder + template in IOTCONNECT.

---

## 10) Common failures and fixes

### `cmox_init.h` missing
CMOX library not installed in SDK. Copy `include/` and `lib/` from X‑CUBE‑CRYPTOLIB into the SDK path.

### `MFG storage: validation failed`
You flashed the wrong manufacturing data or wrong address. Re‑generate using `provision.py st aws --chip WBA55xG` and re‑flash.

### `LittleFS: Corrupted dir pair`
Do **full erase** before flashing firmware + MFG.

---

## 11) BLE‑only notes

`sid_ble` uses **Link Type 1 (BLE)** only. It will not use Sub‑GHz links.  
This is suitable for **demo/validation** and IOTCONNECT integration.

For full Sidewalk (BLE + Sub‑GHz), switch to `sid_demo` and add a supported sub‑GHz radio board.
