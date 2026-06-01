"""
/IOTCONNECT decoder for the WBA55 + IKS4A1 Sidewalk-over-BLE example
(TLV wire format).

Wire format (matches sensors_iks4a1.c in the firmware):
    byte 0      : msg_desc (sid_demo style: status_hdr_ind | opc | cmd_class | cmd_id)
    bytes 1..   : TLV stream

TLV entry layout (sid_demo convention):
    header (1 byte)  : (size_type << 6) | (tag & 0x3F)
                       size_type 0 -> 1-byte length, 1 -> 2-byte, 2 -> 4-byte
    length (size_type bytes, little-endian)
    value  (length bytes, little-endian for multi-byte integers)

Tags emitted by the IKS4A1 firmware:
    0x06  TAG_TEMPERATURE_SENSOR_DATA_NOTIFY  int16 LE deg C (whole)
                                              [kept for STsidewalk2 compat;
                                               this decoder ignores it because
                                               tag 0x24 carries higher precision]
    0x20  IKS4A1_VERSION                     uint8
    0x21  IKS4A1_SEQUENCE                    uint8
    0x22  IKS4A1_ACCEL                       3 x int16 LE mg
    0x23  IKS4A1_GYRO                        3 x int16 LE (dps * 10)
    0x24  IKS4A1_TEMP_STTS22H_X100           int16 LE (deg C * 100)
    0x25  IKS4A1_TEMP_SHT40_X100             int16 LE (deg C * 100)
    0x26  IKS4A1_HUMIDITY_X100               uint16 LE (%RH * 100)
    0x27  IKS4A1_PRESSURE_X100               uint32 LE (hPa * 100)

Output dict matches the attributes defined in
sidewalk_iks4a1_template.json.
"""

import base64
import json


# sid_demo standard tags (from apps/common/sid_demo_parser/include/sid_demo_types.h)
TAG_TEMPERATURE_SENSOR_DATA_NOTIFY  = 0x06
TAG_CURRENT_GPS_TIME_IN_SECONDS     = 0x07
TAG_LINK_TYPE                       = 0x0C

LINK_TYPE_MAP = {1: "BLE", 2: "FSK", 3: "LORA"}

# IKS4A1-specific tags
TAG_IKS4A1_VERSION         = 0x20
TAG_IKS4A1_SEQUENCE        = 0x21
TAG_IKS4A1_ACCEL           = 0x22
TAG_IKS4A1_GYRO            = 0x23
TAG_IKS4A1_TEMP_STTS22H    = 0x24
TAG_IKS4A1_TEMP_SHT40      = 0x25
TAG_IKS4A1_HUMIDITY        = 0x26
TAG_IKS4A1_PRESSURE        = 0x27


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

        elif tag == TAG_TEMPERATURE_SENSOR_DATA_NOTIFY and len(value) >= 2:
            # Whole-degree STTS22H temperature. We also expose it as
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
    # sensors_iks4a1_pack().
    def tlv(tag, value_bytes):
        return bytes([tag, len(value_bytes)]) + value_bytes

    def i16le(v):
        v &= 0xFFFF
        return bytes([v & 0xFF, (v >> 8) & 0xFF])

    def u16le(v):
        return bytes([v & 0xFF, (v >> 8) & 0xFF])

    def u32le(v):
        return bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF])

    msg_desc = bytes([0x40])
    payload = (
        msg_desc
        + tlv(TAG_TEMPERATURE_SENSOR_DATA_NOTIFY, i16le(23))                    # whole C
        + tlv(TAG_IKS4A1_VERSION,         bytes([0x01]))
        + tlv(TAG_IKS4A1_SEQUENCE,        bytes([7]))
        + tlv(TAG_IKS4A1_ACCEL,           i16le(12) + i16le(-8) + i16le(1003))  # mg
        + tlv(TAG_IKS4A1_GYRO,            i16le(15) + i16le(-3) + i16le(22))    # dps*10
        + tlv(TAG_IKS4A1_TEMP_STTS22H,    i16le(2345))                          # 23.45 C
        + tlv(TAG_IKS4A1_TEMP_SHT40,      i16le(2350))                          # 23.50 C
        + tlv(TAG_IKS4A1_HUMIDITY,        u16le(4250))                          # 42.50 %RH
        + tlv(TAG_IKS4A1_PRESSURE,        u32le(101325))                        # 1013.25 hPa
    )

    encoded = base64.b64encode(payload).decode()
    print(f"payload_hex   = {payload.hex()}")
    print(f"payload_size  = {len(payload)} bytes")
    print(f"payload_base64= {encoded}\n")

    out = dict_from_payload(encoded)
    print(json.dumps(out, indent=2))
