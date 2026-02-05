# Geolocation Demo: Teseo (STM32WBA + GNSS)

This guide covers the **Teseo GNSS geolocation demo** in the STM32 Sidewalk SDK and its integration with **IOTCONNECT**.

It assumes:
- You cloned **STM32‑Sidewalk‑SDK**
- You have a **NUCLEO‑WBA55** and a **Teseo GNSS module**
- You want to decode GNSS position uplinks in IOTCONNECT

## 1) Hardware

- NUCLEO‑WBA55CG
- Teseo GNSS module connected per ST demo wiring
- Sub‑GHz radio shield required for Sidewalk dual‑link demos
  - Choose one: **SX126x**, **S2‑LP**, or **STM32WL55**

![NUCLEO-WBA55CG with radio shield options](https://raw.githubusercontent.com/stm32-hotspot/STM32-Sidewalk-SDK/main/pictures/Picture12.jpg)

The Teseo GNSS module connects to the NUCLEO‑WBA55CG per ST demo wiring; the image shows common Sub‑GHz shield options.

---

## 2) CubeIDE Project Selection

Use the Teseo geolocation demo project for your board + radio:

```
STM32-Sidewalk-SDK/apps/st/stm32wba/sid_teseo_geolocation/STM32CubeIDE/
```

Pick the folder that matches your configuration (WBA55 + radio):
- `STM32WBA55_SX126x`
- `STM32WBA55_S2-LP`
- `STM32WBA55_STM32WL55`

Import in STM32CubeIDE:
1. `File > Import...`
2. `General > Existing Projects into Workspace`
3. Select the folder above
4. Build the `Debug` configuration

---

## 3) Generate Manufacturing Data from IOTCONNECT JSON

Use the provisioning tool from the SDK and your IOTCONNECT JSON file:

```
python3 <WORKSPACE_ROOT>/STM32-Sidewalk-SDK/tools/provision/provision.py \
  st aws \
  --chip WBA55xG \
  --certificate_json <DEVICE_JSON>.json \
  --output_bin mfg_wba55.bin \
  --output_hex mfg_wba55.hex
```

---

## 4) Flash Firmware + MFG

Erase:
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -e all
```

Flash firmware `.hex` (from your build output folder):
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -w <FIRMWARE_HEX>.hex
```

Flash manufacturing data:
```
<STM32CUBEPROGRAMMER_DIR>/bin/STM32_Programmer_CLI -c port=SWD -w mfg_wba55.hex
```

---

## 5) IOTCONNECT Decoder

Use:
```
decoders/geolocation_teseo.py
```

This decoder extracts:
- GNSS position (lat, lon, elevation)
- Accuracy metrics
- GNSS timestamp
- MCU temperature
- Demo counter

---

## 6) /IOTCONNECT Device Template

Use:
```
device-templates/sidewalk_teseo_geolocation_template.json
```

---

## 7) Expected Uplink Fields

- `position_time` (ISO8601 UTC string)
- `position_time_epoch`
- `latitude`
- `longitude`
- `elevation`
- `horizontal_accuracy`
- `vertical_accuracy`
- `mcu_temperature`
- `demo_counter`
