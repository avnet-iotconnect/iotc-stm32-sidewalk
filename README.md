# /IOTCONNECT STM32 Amazon Sidewalk Prototype Onboarding

This repository provides **/IOTCONNECT** assets and documentation for **STM32 Sidewalk SDK** examples across multiple board configurations. It is organized to keep **device templates**, **dashboard templates**, **decoders**, and **media** separate, while each example has its own detailed README.

---

## Amazon Sidewalk Production Support in /IOTCONNECT

Production is supported in customer **/IOTCONNECT** instances, but this repository documents **prototype onboarding steps only**. Before production rollout, engage **AWS and the /IOTCONNECT team first** to coordinate Amazon Sidewalk manufacturing-flow enablement in your AWS account/environment.

The provisioning steps documented in this repository are for the **Amazon Sidewalk prototyping flow**.

This means:

- Devices are provisioned using per-device certificate JSON and flashed individually.
- This flow is intended for development, validation, and demos.
- This flow is **not** the Sidewalk factory manufacturing flow for mass production.

### Amazon Sidewalk Prototype restrictions

- Sidewalk prototyping supports up to **1,000 prototype devices**.
- Provisioning is **one device at a time** (no bulk onboarding/import-task flow).
- Not intended for high-volume factory lines.

### Amazon Sidewalk Production / manufacturing customers

Production customers must use the **Amazon Sidewalk manufacturing flow** (HSM + control logs + SMSN + import tasks).

For production onboarding, work with the **/IOTCONNECT team** to integrate the **Amazon Sidewalk** manufacturing flow into your **own AWS account and environment**.

- Manufacturing setup and workflow: https://docs.sidewalk.amazon/manufacturing/sidewalk-manufacturing-setup-works.html
- Sidewalk device lifecycle (prototype vs production): https://docs.sidewalk.amazon/manufacturing/sidewalk-device-lifecycle.html
- Sidewalk bulk provisioning workflow: https://docs.aws.amazon.com/iot-wireless/latest/developerguide/sidewalk-bulk-provisioning-workflow.html
- Provisioning using import tasks: https://docs.aws.amazon.com/iot-wireless/latest/developerguide/sidewalk-provision-bulk-import.html

### Amazon Sidewalk Prototype vs Production

| Area | Prototype flow (documented in this repo) | Production flow (Amazon Sidewalk manufacturing) |
|---|---|---|
| Provisioning method | Per-device certificate JSON + provisioning script (`provision.py`) | Factory provisioning with HSM, control logs, and SMSN |
| Device scale | Up to 1,000 prototype devices | Production scale (manufacturing flow) |
| Onboarding style | One device at a time | Bulk onboarding using import tasks |
| Intended use | Development, testing, demos | Commercial production deployments |
| /IOTCONNECT engagement | Standard templates/decoders integration | Engage /IOTCONNECT team for manufacturing integration in customer AWS account/environment |

---

## Repository Layout

- `device-templates`  
  /IOTCONNECT device templates aligned to specific STM32 Sidewalk examples.

- `dashboard-templates`  
  /IOTCONNECT dashboard templates (optional).

- `decoders`  
  Uplink payload decoders for Sidewalk demo payloads.

- `media`  
  Screenshots, diagrams, or other media assets.

- `examples`  
  Per‑example, step‑by‑step instructions that cover building, provisioning, and flashing.

---

## STM32 Sidewalk SDK Overview

The **STM32 Sidewalk SDK** provides a collection of example applications for multiple STM32WBA configurations. Common example categories include:

- **BLE‑only Sidewalk** (Link Type 1)  
  Useful for fast onboarding and /IOTCONNECT payload validation.

- **BLE + Sub‑GHz Sidewalk**  
  Requires supported Sub‑GHz radios (e.g., SX126x, LR11xx, S2‑LP).  
  These examples demonstrate dual‑link operation and full Sidewalk coverage.

- **Geolocation demos**  
  Examples with GNSS/Wi‑Fi geolocation hardware and cloud integration.

- **OTA / SBDT demos**  
  Demonstrations of Sidewalk Bulk Data Transfer (firmware update flows).

Each example has different build targets and board definitions. Use the README under each example for exact build and provisioning steps.

Typical STM32 Sidewalk hardware pairings (WBA55 with common radio options):

![NUCLEO-WBA55CG example hardware pairings](https://raw.githubusercontent.com/stm32-hotspot/STM32-Sidewalk-SDK/main/pictures/Picture12.jpg)

---

## Example Guides

- **BLE‑only Sidewalk on Nucleo‑WBA55**  
  [examples/ble-wba55/README.md](examples/ble-wba55/README.md)

- **Geolocation: Teseo GNSS (WBA55)**  
  [examples/geolocation-teseo/README.md](examples/geolocation-teseo/README.md)

- **Geolocation: LR11xx (WBA55)**  
  [examples/geolocation-lr11xx/README.md](examples/geolocation-lr11xx/README.md)

- **Sidewalk Demo: WBA55 + LR11xx**  
  [examples/sidewalk-demo-wba55-lr11xx/README.md](examples/sidewalk-demo-wba55-lr11xx/README.md)

- **Sidewalk Demo: WBA55 + S2‑LP**  
  [examples/sidewalk-demo-wba55-s2lp/README.md](examples/sidewalk-demo-wba55-s2lp/README.md)

- **Sidewalk Demo: WBA55 + SX126x**  
  [examples/sidewalk-demo-wba55-sx126x/README.md](examples/sidewalk-demo-wba55-sx126x/README.md)

- **Sidewalk Demo: WBA55 + STM32WL55**  
  [examples/sidewalk-demo-wba55-stm32wl55/README.md](examples/sidewalk-demo-wba55-stm32wl55/README.md)

---

## Next Additions

As more examples are validated, add:
- A decoder under `decoders/`
- A device template under `device-templates/`
- A per‑example README under `examples/`
