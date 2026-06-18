# Sidewalk WBA55 Firmware + Provisioning

Pre-built firmware images and per-device Sidewalk manufacturing data for the
**Nucleo-WBA55CG + X-NUCLEO-IKSxA1** demo. Pair the correct firmware with the
matching sensor expansion board and flash both the firmware and a device's
`mfg.bin` to bring a unit online.

## Contents

```
binaries/
├── sid_ble_wba55_iks4a1.hex    # firmware for boards with X-NUCLEO-IKS4A1
├── sid_ble_wba55_iks5a1.hex    # firmware for boards with X-NUCLEO-IKS5A1
└── sidewalk-mfg/               # NOT COMMITTED — contains private keys
    └── <device-name>/
        ├── cert.json           # AWS-provided cert (PRIVATE KEY — do not share)
        ├── mfg.bin             # WBA55-format manufacturing image
        └── mfg.hex             # same content, hex form
```

The two firmware hexes are reproducible from the SDK, so they are
intentionally `.gitignore`d. Run `../scripts/build-firmware.sh` to rebuild.

The `sidewalk-mfg/` directory is **never committed** — `cert.json` contains
device private keys.

## Sensor board → firmware mapping

| Physical board | Firmware hex | Sensors populated in /IOTCONNECT |
|---|---|---|
| Nucleo-WBA55CG + **X-NUCLEO-IKS4A1** | `sid_ble_wba55_iks4a1.hex` | accel, gyro, STTS22H temp, SHT40 temp + humidity, LPS22DF pressure, LSM6DSV16X 6D orientation, LIS2DUXS12 Qvar |
| Nucleo-WBA55CG + **X-NUCLEO-IKS5A1** | `sid_ble_wba55_iks5a1.hex` | accel, gyro, ILPS22QS temp + pressure, IIS2DULPX Qvar *(no SHT40, no orientation)* |

## Prerequisites

* **STM32CubeProgrammer CLI** on PATH as `STM32_Programmer_CLI`
* **Python 3** (for `provision.py`)
* **STM32-Sidewalk-SDK** checked out — defaults to `~/dev/sidewalk/STM32-Sidewalk-SDK`. The provisioning script uses its bundled `tools/provision/provision.py`.

## Step 1 — Generate the manufacturing image for a new device

You should have a cert JSON file from AWS IoT Wireless when you provisioned the
Sidewalk device (e.g. `mclST5A3.json` downloaded to `~/Downloads/`).

```bash
cd ~/dev/sidewalk/iotc-stm32-sidewalk
./scripts/provision-device.sh <device-name> <path-to-cert.json>
```

Example:

```bash
./scripts/provision-device.sh mclST5A3 ~/Downloads/mclST5A3.json
```

This will produce:

```
binaries/sidewalk-mfg/mclST5A3/
├── cert.json
├── mfg.bin      <-- flash this @ 0x080FE000
└── mfg.hex
```

The script enforces `chmod 700` on the directory and `chmod 600` on the cert /
mfg files. It also prints the flash command for that specific device.

## Step 2 — Flash the device

The MCU is fully erased before flashing, so any existing Sidewalk registration
on the chip is wiped. After the flash, the device performs a fresh Sidewalk
registration on first boot.

### IKS4A1-equipped board

```bash
cd ~/dev/sidewalk/iotc-stm32-sidewalk/binaries

STM32_Programmer_CLI -c port=SWD mode=UR -e all
STM32_Programmer_CLI -c port=SWD mode=UR -d sid_ble_wba55_iks4a1.hex -v
STM32_Programmer_CLI -c port=SWD mode=UR -d sidewalk-mfg/<device>/mfg.bin 0x080FE000 -v
```

### IKS5A1-equipped board

```bash
cd ~/dev/sidewalk/iotc-stm32-sidewalk/binaries

STM32_Programmer_CLI -c port=SWD mode=UR -e all
STM32_Programmer_CLI -c port=SWD mode=UR -d sid_ble_wba55_iks5a1.hex -v
STM32_Programmer_CLI -c port=SWD mode=UR -d sidewalk-mfg/<device>/mfg.bin 0x080FE000 -v
```

> If `STM32_Programmer_CLI` returns `DEV_CONNECT_ERR` repeatedly, **hold the
> black RESET button** on the Nucleo board while the command starts. The
> WBA55 enters Stop2 / Standby low-power modes between Sidewalk BLE
> advertising windows, which gates the SWD debug pads. Holding RESET keeps
> the CPU out of LPM long enough for the programmer to attach. After the
> first successful flash with the current firmware, subsequent connects
> should work without holding RESET (the firmware enables
> `DBGMCU_EnableDBGStopMode` + `EnableDBGStandbyMode` unconditionally).

## Verifying a flash worked

Open the Nucleo's USB serial port at 115200 8N1. On boot you should see:

```
[INFO]: Host MCU: STM32WBA5x (0x492), revision: Rev. B (0x2000)
[INFO]: MFG storage: validation passed
[INFO]: Sidewalk demo started
[INFO]: Sidewalk registration status: Not registered      (first boot only)
...
[INFO]: Sidewalk Device Registration done                 (first boot only)
[INFO]: Sending counter update: 0
[INFO]: Sent message(type: 2, id: 1)
```

Subsequent boots will say `Sidewalk registration status: Registered` and skip
the ECPFG flow.

After the first uplink reaches the gateway, the corresponding record should
appear in /IOTCONNECT under the device's name (template `STsideIKA4`, decoder
`sidewalk-iks4a1-tlv`). Send cadence is ~1 uplink per 2 minutes — the gap
matches Sidewalk's BLE re-acquisition window, not the firmware's demo timer.

## Rebuilding firmware

Whenever the SDK firmware source changes, rebuild and refresh the hexes here:

```bash
cd ~/dev/sidewalk/iotc-stm32-sidewalk
./scripts/build-firmware.sh           # both variants
./scripts/build-firmware.sh iks4a1    # IKS4A1 only
./scripts/build-firmware.sh iks5a1    # IKS5A1 only
```

The script handles the `.cproject` flag flip between the two variants and
restores the default (IKS4A1=1) on exit.

## Security note

`sidewalk-mfg/<device>/cert.json` contains device-bound private keys. Treat
each device's `sidewalk-mfg/<device>/` directory as you would a `.ssh/`
folder:

* never commit it (already `.gitignore`d)
* never paste cert.json into chat / email / tickets
* delete the directory after flashing if the build host isn't the device's
  long-term keeper
