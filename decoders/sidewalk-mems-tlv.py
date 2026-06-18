"""
/IOTCONNECT decoder for the WBA55 + X-NUCLEO MEMS sensor Sidewalk-over-BLE demo.

Supports both X-NUCLEO-IKS4A1 and X-NUCLEO-IKS5A1 firmware variants. Both
emit the same sid_demo TLV wire format; the only difference between boards
is which subset of tags is populated:

  X-NUCLEO-IKS4A1 emits :  acc, gyro, STTS22H temp, SHT40 temp+RH, LPS22DF pressure,
                           LSM6DSV16X 6D orientation, LIS2DUXS12 Qvar
  X-NUCLEO-IKS5A1 emits :  acc, gyro, ILPS22QS temp (under stts22h tag),
                           ILPS22QS pressure (under lps22df tag), IIS2DULPX Qvar
                           (no SHT40, orientation = "unknown" until ISM6HG256X
                            6D engine is wired in firmware)

Output fields for "missing" sensors stay empty rather than being omitted, so a
single /IOTCONNECT template covers both boards.

Wire format (matches sensors_iks4a1.c / sensors_iks5a1.c in the firmware):
    byte 0      : msg_desc (sid_demo style: status_hdr_ind | opc | cmd_class | cmd_id)
    bytes 1..   : TLV stream

TLV entry layout (sid_demo convention):
    header (1 byte)  : (size_type << 6) | (tag & 0x3F)
                       size_type 0 -> 1-byte length, 1 -> 2-byte, 2 -> 4-byte
    length (size_type bytes, little-endian)
    value  (length bytes, little-endian for multi-byte integers)

Tags emitted by the MEMS firmware:
    0x06  TAG_TEMPERATURE_SENSOR_DATA_NOTIFY  int16 LE deg C (whole)
                                              -> sensor_data (int) + Temperature (float)
    0x07  TAG_CURRENT_GPS_TIME_IN_SECONDS     uint32 LE seconds since GPS epoch
    0x0C  TAG_LINK_TYPE                       uint8 (1=BLE, 2=FSK, 3=LORA)
    0x20  IKS4A1_VERSION                      uint8 payload schema version
    0x21  IKS4A1_SEQUENCE                     uint8 application sequence counter
    0x22  IKS4A1_ACCEL                        3 x int16 LE mg
    0x23  IKS4A1_GYRO                         3 x int16 LE (dps * 10)
    0x24  IKS4A1_TEMP_STTS22H_X100            int16 LE (deg C * 100)
    0x25  IKS4A1_TEMP_SHT40_X100              int16 LE (deg C * 100)   [IKS4A1 only]
    0x26  IKS4A1_HUMIDITY_X100                uint16 LE (%RH * 100)    [IKS4A1 only]
    0x27  IKS4A1_PRESSURE_X100                uint32 LE (hPa * 100)
    0x28  IKS4A1_ORIENTATION                  uint8 enum               [IKS4A1 only]
    0x29  IKS4A1_QVAR_RAW                     int16 LE raw count

Output dict matches the attributes defined in sidewalk_iks4a1_template.json
(which is also reused as-is for IKS5A1).
"""

import base64
import json


# sid_demo standard tags (from apps/common/sid_demo_parser/include/sid_demo_types.h)
TAG_TEMPERATURE_SENSOR_DATA_NOTIFY  = 0x06
TAG_CURRENT_GPS_TIME_IN_SECONDS     = 0x07
TAG_LINK_TYPE                       = 0x0C

LINK_TYPE_MAP = {1: "BLE", 2: "FSK", 3: "LORA"}

# IKS4A1/IKS5A1-specific tags. The macro prefix is "IKS4A1" historically
# (the IKS4A1 firmware shipped first); the IKS5A1 firmware reuses the same
# wire format so a single decoder and template work for both.
TAG_IKS4A1_VERSION         = 0x20
TAG_IKS4A1_SEQUENCE        = 0x21
TAG_IKS4A1_ACCEL           = 0x22
TAG_IKS4A1_GYRO            = 0x23
TAG_IKS4A1_TEMP_STTS22H    = 0x24
TAG_IKS4A1_TEMP_SHT40      = 0x25
TAG_IKS4A1_HUMIDITY        = 0x26
TAG_IKS4A1_PRESSURE        = 0x27
TAG_IKS4A1_ORIENTATION     = 0x28
TAG_IKS4A1_QVAR_RAW        = 0x29
TAG_IKS4A1_MLC1            = 0x2A   # LSM6DSV16X MLC1_SRC label, asset_tracking UCF
TAG_IKS4A1_MLC1_MODEL      = 0x2B   # u8, model ID identifying which UCF produced the raw value

# Maps sensors_iks4a1_orient_t (firmware enum) -> human-readable string for the
# IOTCONNECT dashboard. UNKNOWN = mid-tilt (no axis aligned with gravity above
# the 6D threshold) OR the IKS5A1 build, which doesn't expose 6D yet.
ORIENT_MAP = {
    0: "unknown",
    1: "landscape_right",   # +X face up
    2: "landscape_left",    # -X face up
    3: "portrait_up",       # +Y face up
    4: "portrait_down",     # -Y face up
    5: "face_up",           # +Z face up
    6: "face_down",         # -Z face up
}

# LSM6DSV16X MLC1_SRC label dictionaries keyed by model ID. The firmware
# emits tag 0x2B (TAG_IKS4A1_MLC1_MODEL) alongside tag 0x2A (mlc1_raw) so the
# decoder knows which dictionary to pick: changing the UCF in firmware bumps
# the model ID, the decoder routes to the matching label set, and old
# decoders that don't know a new model ID gracefully surface the raw integer
# untranslated (no crash, just no label).
#
# Keep these values in sync with the SENSORS_IKS4A1_MLC1_MODEL_* macros in
# sensors_iks4a1.h. When you add a new .ucf, register both its model ID name
# and its label map below — that's the only file the cloud side needs to
# learn about the new model.
MLC1_MODEL_NONE              = 0
MLC1_MODEL_ASSET_TRACKING    = 1
MLC1_MODEL_ACTIVITY_MOBILE   = 2
MLC1_MODEL_ACTIVITY_WRIST    = 3
MLC1_MODEL_GYM_ACTIVITY      = 4
MLC1_MODEL_HEAD_GESTURES     = 5
MLC1_MODEL_YOGA_POSE         = 6

MLC1_MODEL_NAMES = {
    MLC1_MODEL_NONE:            "none",
    MLC1_MODEL_ASSET_TRACKING:  "asset_tracking",
    MLC1_MODEL_ACTIVITY_MOBILE: "activity_recognition_for_mobile",
    MLC1_MODEL_ACTIVITY_WRIST:  "activity_recognition_for_wrist",
    MLC1_MODEL_GYM_ACTIVITY:    "gym_activity_recognition",
    MLC1_MODEL_HEAD_GESTURES:   "head_gestures",
    MLC1_MODEL_YOGA_POSE:       "yoga_pose_recognition",
}

MLC1_LABEL_MAPS = {
    MLC1_MODEL_ASSET_TRACKING: {
        0:  "stationary_upright",
        4:  "stationary_not_upright",
        8:  "in_motion",
        12: "shaken",
    },
    MLC1_MODEL_ACTIVITY_MOBILE: {
        0:  "stationary",
        1:  "walking",
        4:  "jogging",
        8:  "biking",
        12: "driving",
    },
    # When you load a new .ucf, register its label map here keyed by the
    # matching model ID. See https://github.com/STMicroelectronics/STMems_Machine_Learning_Core/
    # tree/master/application_examples/lsm6dsv16x for each model's README,
    # which documents the exact MLC1_SRC -> label mapping.
}


def _read_tlv(data, offset):
    if offset >= len(data):
        raise ValueError("TLV parse: unexpected end of buffer")
    header = data[offset]
    offset += 1
    size_type = (header >> 6) & 0x3
    tag = header & 0x3F

    if size_type == 0:
        size_len = 1
    elif size_type == 1:
        size_len = 2
    elif size_type == 2:
        size_len = 4
    else:
        raise ValueError("TLV parse: invalid size type")

    if offset + size_len > len(data):
        raise ValueError("TLV parse: truncated length")
    length = int.from_bytes(data[offset:offset + size_len], byteorder="little")
    offset += size_len

    if offset + length > len(data):
        raise ValueError("TLV parse: truncated value")
    value = data[offset:offset + length]
    offset += length
    return tag, length, value, offset


def _i16_le(b):
    v = int.from_bytes(b, byteorder="little", signed=False)
    if v >= 0x8000:
        v -= 0x10000
    return v


def _parse(data):
    if len(data) < 1:
        raise ValueError("Decoded data must be at least 1 byte.")

    msg_desc = data[0]
    status_hdr_ind = (msg_desc >> 7) & 0x1
    opc            = (msg_desc >> 5) & 0x3
    cmd_class      = (msg_desc >> 3) & 0x3
    cmd_id         =  msg_desc       & 0x7

    offset = 1
    if status_hdr_ind:
        if len(data) < 2:
            raise ValueError("Decoded data missing status code.")
        offset = 2

    payload = data[offset:]

    # Template-required defaults (so /IOTCONNECT does not drop the record if a
    # particular sensor read failed and produced no TLV entry).
    result = {
        "id": f"{opc}-{cmd_class}-{cmd_id}",
        "Sequence": 0,
        "Sinewave": 0,
        "version": 0,
        "payload_size": len(data),
    }

    tlv_off = 0
    while tlv_off < len(payload):
        tag, length, value, tlv_off = _read_tlv(payload, tlv_off)

        if tag == TAG_IKS4A1_VERSION and len(value) >= 1:
            result["version"] = int(value[0])

        elif tag == TAG_IKS4A1_SEQUENCE and len(value) >= 1:
            result["Sequence"] = int(value[0])

        elif tag == TAG_IKS4A1_ACCEL and len(value) >= 6:
            ax = _i16_le(value[0:2])
            ay = _i16_le(value[2:4])
            az = _i16_le(value[4:6])
            result["acc_x_g"] = round(ax / 1000.0, 3)
            result["acc_y_g"] = round(ay / 1000.0, 3)
            result["acc_z_g"] = round(az / 1000.0, 3)

        elif tag == TAG_IKS4A1_GYRO and len(value) >= 6:
            gx = _i16_le(value[0:2])
            gy = _i16_le(value[2:4])
            gz = _i16_le(value[4:6])
            result["gyr_x_dps"] = round(gx / 10.0, 1)
            result["gyr_y_dps"] = round(gy / 10.0, 1)
            result["gyr_z_dps"] = round(gz / 10.0, 1)

        elif tag == TAG_IKS4A1_TEMP_STTS22H and len(value) >= 2:
            result["temp_stts22h_c"] = round(_i16_le(value[0:2]) / 100.0, 2)

        elif tag == TAG_IKS4A1_TEMP_SHT40 and len(value) >= 2:
            result["temp_sht40_c"] = round(_i16_le(value[0:2]) / 100.0, 2)

        elif tag == TAG_IKS4A1_HUMIDITY and len(value) >= 2:
            rh = int.from_bytes(value[0:2], byteorder="little", signed=False)
            result["humidity_sht40_pct"] = round(rh / 100.0, 2)

        elif tag == TAG_IKS4A1_PRESSURE and len(value) >= 4:
            p = int.from_bytes(value[0:4], byteorder="little", signed=False)
            result["pressure_hpa"] = round(p / 100.0, 2)

        elif tag == TAG_IKS4A1_ORIENTATION and len(value) >= 1:
            result["orientation"] = ORIENT_MAP.get(int(value[0]), f"orient_{int(value[0])}")

        elif tag == TAG_IKS4A1_QVAR_RAW and len(value) >= 2:
            result["qvar"] = _i16_le(value[0:2])

        elif tag == TAG_IKS4A1_MLC1 and len(value) >= 1:
            result["mlc1_raw"] = int(value[0])

        elif tag == TAG_IKS4A1_MLC1_MODEL and len(value) >= 1:
            result["mlc1_model_id"] = int(value[0])

        elif tag == TAG_TEMPERATURE_SENSOR_DATA_NOTIFY and len(value) >= 2:
            # Whole-degree STTS22H/ILPS22QS temperature. We also expose it as
            # `sensor_data` / `Temperature` (matching the sid_demo decoder)
            # so the standard /IOTCONNECT sid_demo template fields populate.
            t = _i16_le(value[0:2])
            result["sensor_data"] = int(t)
            result["Temperature"] = float(t)

        elif tag == TAG_CURRENT_GPS_TIME_IN_SECONDS and len(value) >= 4:
            result["gps_time"] = int.from_bytes(value[0:4], byteorder="little", signed=False)

        elif tag == TAG_LINK_TYPE and len(value) >= 1:
            result["link_type"] = LINK_TYPE_MAP.get(value[0], f"LINK_{value[0]}")

        # Unknown tags are silently skipped (sid_demo convention).

    # Post-parse: resolve the MLC1 label using whichever model ID the
    # firmware reported. Done after the TLV loop so the on-wire emit order
    # of tag 0x2A (raw) and tag 0x2B (model_id) doesn't matter. If the
    # firmware predates model_id (no 0x2B on the wire), assume
    # asset_tracking — that's the only model that shipped before tag 0x2B
    # was added, so this preserves backward compatibility.
    if "mlc1_raw" in result:
        model_id = result.get("mlc1_model_id", MLC1_MODEL_ASSET_TRACKING)
        result["mlc1_model_id"]   = model_id
        result["mlc1_model_name"] = MLC1_MODEL_NAMES.get(model_id, f"unknown_model_{model_id}")
        label_map = MLC1_LABEL_MAPS.get(model_id)
        if label_map is None:
            # Decoder doesn't know this model — surface the raw integer
            # rather than guessing. Operator can either deploy a newer
            # decoder or extend MLC1_LABEL_MAPS above.
            result["mlc1_label"] = f"raw_{result['mlc1_raw']}"
        else:
            result["mlc1_label"] = label_map.get(result["mlc1_raw"], f"transition_{result['mlc1_raw']}")

    return result


def _maybe_unwrap_hex_string(data: bytes) -> bytes:
    """AWS IoT Wireless delivers Sidewalk payloads as
       base64(hex_ascii_string_of_raw_bytes), so the first base64 decode
       lands us at an ASCII hex string rather than the raw payload. Detect
       that case (all printable hex characters, even length, first decoded
       byte in the sid_demo NOTIFY msg_desc range 0x40-0x5F — covering
       capability (0x40), action (0x41), and any future cmd_id variants)
       and apply the second decode. /IOTCONNECT's ingestion pipeline
       normalizes this before invoking the decoder, so a single decode
       suffices there. Either way we end up with the raw payload bytes."""
    if len(data) < 2 or len(data) % 2 != 0:
        return data
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return data
    if not all(c in "0123456789abcdefABCDEF" for c in text):
        return data
    # Looks like an even-length hex ASCII string. Confirm the first decoded
    # byte is a plausible sid_demo NOTIFY msg_desc before unwrapping, so a
    # coincidentally hex-looking binary payload isn't mis-unwrapped.
    try:
        first_byte = int(text[:2], 16)
    except ValueError:
        return data
    if not (0x40 <= first_byte <= 0x5F):
        return data
    return bytes.fromhex(text)


def dict_from_payload(base64_input: str, fport: int = None):
    try:
        data = base64.b64decode(base64_input)
    except Exception as e:
        raise ValueError(f"Invalid base64 input: {e}")

    data = _maybe_unwrap_hex_string(data)
    return {"payload": _parse(data)}


# Local self-test
if __name__ == "__main__":
    # Build a synthetic TLV payload that mirrors what the firmware emits for
    # one sensor read, then decode it. This is the inverse of the firmware's
    # sensors_iks4a1_pack() / sensors_iks5a1.c's pack function.
    def tlv(tag, value_bytes):
        return bytes([tag, len(value_bytes)]) + value_bytes

    def i16le(v):
        v &= 0xFFFF
        return bytes([v & 0xFF, (v >> 8) & 0xFF])

    def u16le(v):
        return bytes([v & 0xFF, (v >> 8) & 0xFF])

    def u32le(v):
        return bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF])

    # msg_desc 0x40 reflects the current workaround firmware (CAP). The decoder
    # also accepts 0x41 (ACTION) — the next firmware drop will switch to 0x41
    # without requiring a redeploy of this decoder.
    msg_desc = bytes([0x40])
    payload = (
        msg_desc
        + tlv(TAG_TEMPERATURE_SENSOR_DATA_NOTIFY, i16le(23))                    # whole C
        + tlv(TAG_CURRENT_GPS_TIME_IN_SECONDS,    u32le(1465738392))            # GPS-epoch s
        + tlv(TAG_LINK_TYPE,                      bytes([0x01]))                # BLE
        + tlv(TAG_IKS4A1_VERSION,         bytes([0x01]))
        + tlv(TAG_IKS4A1_SEQUENCE,        bytes([7]))
        + tlv(TAG_IKS4A1_ACCEL,           i16le(12) + i16le(-8) + i16le(1003))  # mg
        + tlv(TAG_IKS4A1_GYRO,            i16le(15) + i16le(-3) + i16le(22))    # dps*10
        + tlv(TAG_IKS4A1_TEMP_STTS22H,    i16le(2345))                          # 23.45 C
        + tlv(TAG_IKS4A1_TEMP_SHT40,      i16le(2350))                          # 23.50 C
        + tlv(TAG_IKS4A1_HUMIDITY,        u16le(4250))                          # 42.50 %RH
        + tlv(TAG_IKS4A1_PRESSURE,        u32le(101325))                        # 1013.25 hPa
        + tlv(TAG_IKS4A1_ORIENTATION,     bytes([0x05]))                        # face_up
        + tlv(TAG_IKS4A1_QVAR_RAW,        i16le(-237))                          # raw count
        + tlv(TAG_IKS4A1_MLC1,            bytes([0x08]))                        # in_motion
        + tlv(TAG_IKS4A1_MLC1_MODEL,      bytes([MLC1_MODEL_ASSET_TRACKING]))   # asset_tracking
    )

    encoded = base64.b64encode(payload).decode()
    print(f"payload_hex   = {payload.hex()}")
    print(f"payload_size  = {len(payload)} bytes")
    print(f"payload_base64= {encoded}\n")

    out = dict_from_payload(encoded)
    print(json.dumps(out, indent=2))
