import base64
import json
import struct
from datetime import datetime, timezone


TAG_GNSS_POSITION = 0x60
TAG_MCU_TEMPERATURE = 0x37
TAG_COUNTER_VALUE = 0xC7


def _read_tlv(data, offset):
    if offset + 2 > len(data):
        raise ValueError("TLV parse: truncated header")
    tag = data[offset]
    length = data[offset + 1]
    offset += 2
    if offset + length > len(data):
        raise ValueError("TLV parse: truncated value")
    value = data[offset:offset + length]
    offset += length
    return tag, length, value, offset


def _parse_gnss_position(value):
    if len(value) < 24:
        raise ValueError("GNSS position payload too short")
    ts_epoch = int.from_bytes(value[0:4], byteorder="big", signed=False)
    latitude = struct.unpack(">f", value[4:8])[0]
    longitude = struct.unpack(">f", value[8:12])[0]
    elevation = struct.unpack(">f", value[12:16])[0]
    h_acc = struct.unpack(">f", value[16:20])[0]
    v_acc = struct.unpack(">f", value[20:24])[0]
    ts_iso = datetime.fromtimestamp(ts_epoch, timezone.utc).isoformat()
    return {
        "timestamp_epoch": ts_epoch,
        "timestamp_iso": ts_iso,
        "latitude": latitude,
        "longitude": longitude,
        "elevation": elevation,
        "horizontal_accuracy": h_acc,
        "vertical_accuracy": v_acc,
    }


def dict_from_payload(base64_input: str, fport: int = None):
    try:
        data = base64.b64decode(base64_input)
    except Exception as e:
        raise ValueError(f"Invalid base64 input: {e}")

    payload = {}
    offset = 0
    while offset < len(data):
        tag, length, value, offset = _read_tlv(data, offset)
        if tag == TAG_GNSS_POSITION:
            pos = _parse_gnss_position(value)
            payload["position_time"] = pos["timestamp_iso"]
            payload["position_time_epoch"] = pos["timestamp_epoch"]
            payload["latitude"] = pos["latitude"]
            payload["longitude"] = pos["longitude"]
            payload["elevation"] = pos["elevation"]
            payload["horizontal_accuracy"] = pos["horizontal_accuracy"]
            payload["vertical_accuracy"] = pos["vertical_accuracy"]
        elif tag == TAG_MCU_TEMPERATURE:
            if len(value) >= 2:
                temp = int.from_bytes(value[0:2], byteorder="big", signed=True)
                payload["mcu_temperature"] = temp
        elif tag == TAG_COUNTER_VALUE:
            payload["demo_counter"] = int.from_bytes(value, byteorder="big", signed=False)

    return {"payload": payload}


if __name__ == "__main__":
    # Example: decode a base64 string (replace with real payload)
    example = ""
    if example:
        print(json.dumps(dict_from_payload(example), indent=2))
