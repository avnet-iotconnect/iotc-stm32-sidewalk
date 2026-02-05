# Sidewalk Demo (WBA55 + S2‑LP)

This guide covers the **Sidewalk demo** application for **NUCLEO‑WBA55** with an **S2‑LP** sub‑GHz radio.

## 1) Hardware

- NUCLEO‑WBA55CG
- S2‑LP radio shield

![NUCLEO-WBA55CG + X-NUCLEO-S2915A1](https://raw.githubusercontent.com/stm32-hotspot/STM32-Sidewalk-SDK/main/pictures/Picture40.jpg)

---

## 2) CubeIDE Project

Project folder:
```
STM32-Sidewalk-SDK/apps/st/stm32wba/sid_demo/STM32CubeIDE/STM32WBA55_S2-LP
```

Import into STM32CubeIDE:
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

Flash firmware `.hex` from your build output:
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
decoders/stsidewalk.py
```

---

## 6) /IOTCONNECT Device Template

Use:
```
device-templates/sidewalk_st_demo_template.json
```
