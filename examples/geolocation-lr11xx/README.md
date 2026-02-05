# Geolocation Demo: LR11xx (STM32WBA + Wi‑Fi/GNSS Scans)

This guide covers the **LR11xx geolocation demo** in the STM32 Sidewalk SDK and its integration with **IOTCONNECT**.

It assumes:
- You cloned **STM32‑Sidewalk‑SDK**
- You have a **NUCLEO‑WBA55** and an **LR11xx** transceiver
- You want to decode Wi‑Fi/GNSS scan uplinks in IOTCONNECT

---

## Images

![NUCLEO‑WBA55 (example)](https://commons.wikimedia.org/wiki/Special:FilePath/Nucleo-board.jpg)
![LoRa radio module (example)](https://commons.wikimedia.org/wiki/Special:FilePath/LoRa_Module_with_antenna_and_SPI_wires_attached.jpg)

---

## 1) Hardware

- NUCLEO‑WBA55CG
- LR11xx radio module (LR1110/LR1120)

---

## 2) CubeIDE Project Selection

Use the LR11xx geolocation demo project:

```
STM32-Sidewalk-SDK/apps/st/stm32wba/sid_lr11xx_geolocation/STM32CubeIDE/STM32WBA55_LR11xx
```

Import in STM32CubeIDE:
1. `File > Import...`
2. `General > Existing Projects into Workspace`
3. Select the folder above
4. Build the `Debug` configuration

---

## 3) Generate Manufacturing Data from IOTCONNECT JSON

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

Flash firmware `.hex`:
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
decoders/geolocation_lr11xx.py
```

This decoder extracts:
- Wi‑Fi scan data (BSSIDs + RSSI)
- NAV3 GNSS scan messages
- Assist position (if provided)
- MCU temperature
- Demo counter

---

## 6) /IOTCONNECT Device Template

Use:
```
device-templates/sidewalk_lr11xx_geolocation_template.json
```

---

## 7) Expected Uplink Fields

- `wifi_scans` (JSON string)
- `nav3_messages` (JSON string)
- `assist_position_lat`
- `assist_position_lon`
- `mcu_temperature`
- `demo_counter`
