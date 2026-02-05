import base64
import json
from datetime import datetime, timezone


TAG_COUNTER_VALUE = 0xC7
TAG_MCU_TEMPERATURE = 0x37
TAG_WIFI_SCAN_DATA = 0x3F
TAG_NAV3_NO_AP_SCAN_DATA = 0x62
TAG_NAV3_AP_SCAN_DATA = 0x63


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


def _parse_wifi_scan_data(value):
    scans = []
    idx = 0
    while idx + 7 <= len(value):
        mac = value[idx:idx + 6]
        rssi = int.from_bytes(value[idx + 6:idx + 7], byteorder="big", signed=True)
        idx += 7
        mac_str = ":".join(f"{b:02X}" for b in mac)
        scans.append({"mac_address": mac_str, "rssi": rssi})
    return scans


def _convert_raw_timestamp_to_gps_timestamp(raw_ts):
    # Based on ST geolocation lambda parser logic
    current_utc = datetime.now(timezone.utc)
    jan_6_1980 = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
    seconds_per_week = 60 * 60 * 24 * 7
    full_1024_weeks = int((current_utc - jan_6_1980).total_seconds() // seconds_per_week // 1024)
    return int(raw_ts + full_1024_weeks * seconds_per_week * 1024)


def _parse_nav3_scan_data(value):
    scans = []
    if len(value) < 2:
        return scans
    # First 2 bytes: time accuracy
    time_acc = (int.from_bytes(value[0:2], "big") + 1) / 4096.0
    idx = 2
    while idx + 5 <= len(value):
        raw_ts = int.from_bytes(value[idx:idx + 4], "big")
        idx += 4
        nav_len = value[idx]
        idx += 1
        if idx + nav_len > len(value):
            break
        nav_payload = value[idx:idx + nav_len].hex()
        idx += nav_len
        scans.append({
            "timestamp": _convert_raw_timestamp_to_gps_timestamp(raw_ts),
            "time_accuracy": time_acc,
            "nav3_payload": nav_payload
        })
    return scans


def _parse_nav3_with_ap_scan_data(value):
    if len(value) < 4:
        return {"assist_position": None, "nav3_messages": []}
    ap_lat = int.from_bytes(value[0:2], "big", signed=True) * 90.0 / 2048.0
    ap_lon = int.from_bytes(value[2:4], "big", signed=True) * 180.0 / 2048.0
    nav3 = _parse_nav3_scan_data(value[4:])
    return {"assist_position": {"latitude": ap_lat, "longitude": ap_lon}, "nav3_messages": nav3}


def dict_from_payload(base64_input: str, fport: int = None):
    try:
        data = base64.b64decode(base64_input)
    except Exception as e:
        raise ValueError(f"Invalid base64 input: {e}")

    payload = {}
    offset = 0
    while offset < len(data):
        tag, length, value, offset = _read_tlv(data, offset)
        if tag == TAG_WIFI_SCAN_DATA:
            payload["wifi_scans"] = json.dumps(_parse_wifi_scan_data(value))
        elif tag == TAG_NAV3_NO_AP_SCAN_DATA:
            payload["nav3_messages"] = json.dumps(_parse_nav3_scan_data(value))
        elif tag == TAG_NAV3_AP_SCAN_DATA:
            parsed = _parse_nav3_with_ap_scan_data(value)
            if parsed["assist_position"]:
                payload["assist_position_lat"] = parsed["assist_position"]["latitude"]
                payload["assist_position_lon"] = parsed["assist_position"]["longitude"]
            payload["nav3_messages"] = json.dumps(parsed["nav3_messages"])
        elif tag == TAG_MCU_TEMPERATURE:
            if len(value) >= 2:
                payload["mcu_temperature"] = int.from_bytes(value[0:2], "big", signed=True)
        elif tag == TAG_COUNTER_VALUE:
            payload["demo_counter"] = int.from_bytes(value, "big", signed=False)

    return {"payload": payload}


if __name__ == "__main__":
    example = ""
    if example:
        print(json.dumps(dict_from_payload(example), indent=2))
