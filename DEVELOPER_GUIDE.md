# Developer Guide: STM32 Amazon Sidewalk with /IOTCONNECT

This guide holds the detail that [Getting Started](GETTING_STARTED_WBA.md) leaves out. Read it when you want to understand, test, or change how the demo works, rather than just bring a board online.

For building the firmware see [Build Setup](BUILD_SETUP.md). For the firmware itself, the payload wire format, and downlink commands see the [MEMS example README](examples/sidewalk-mems-wba55/README.md).

## Table of Contents

1. [The uplink decoder](#the-uplink-decoder)
   * [Where the decoder runs](#where-the-decoder-runs)
   * [Decoder types](#decoder-types)
   * [The decoder in this repo](#the-decoder-in-this-repo)
   * [Test the decoder locally](#test-the-decoder-locally)

---

## The uplink decoder

Sidewalk is a low-bandwidth network, so the firmware does not send JSON. It packs each reading into a compact binary **TLV** (tag-length-value) frame, a few dozen bytes carrying accelerometer, gyro, temperature, pressure, and Qvar values. That frame arrives in the cloud as base64. A **decoder** is the small piece of Python that turns those bytes back into named values.

### Where the decoder runs

```
Board  ──BLE──▶  Sidewalk gateway  ──▶  AWS IoT Wireless  ──▶  /IOTCONNECT Lambda
(packs TLV)         (Echo / Ring)         (deduplicates)         (runs the DECODER)
                                                                        │
                                              dashboards & rules  ◀── template attributes
                                                                   (JSON mapped by name)
```

The decoder runs inside the /IOTCONNECT Lambda, before the platform stores anything. Its output keys are matched **by name, case-sensitively**, against the attributes declared in your device template. An attribute the decoder never emits stays empty, and a key with no matching attribute is discarded. That name mismatch is the most common reason a device shows as connected but never populates Live Data.

### Decoder types

| Decoder | Use |
|---|---|
| **Raw Data Default** | Passes the raw payload straight through. Useful only to confirm bytes are arriving. |
| **Custom Decoder** | Your own Python, mapping the payload to template attributes. This is what the demo uses. |

### The decoder in this repo

The custom decoder is [`decoders/sidewalk-mems-tlv.py`](decoders/sidewalk-mems-tlv.py). It walks the TLV stream, skips unknown tags rather than failing, and returns scaled SI values (g, dps, °C, %RH, hPa) under exactly the names the `STswMEMS` template declares. One decoder serves both sensor boards; the IKS5A1 simply leaves the fields it has no sensor for empty.

/IOTCONNECT decoders use a fixed entry point:

```python
def dict_from_payload(base64_input: str, fport: int = None):
    return {"payload": {...}}
```

Custom decoders are reviewed by /IOTCONNECT before they can run in the cloud. Submitting one is covered in [Getting Started, Step 4](GETTING_STARTED_WBA.md#decoder).

### Test the decoder locally

You can run the decoder before uploading anything. It builds a synthetic payload, decodes it, and prints the result. Expect about 23 °C, 42 %RH, and 1013 hPa:

```
python decoders/sidewalk-mems-tlv.py
```
