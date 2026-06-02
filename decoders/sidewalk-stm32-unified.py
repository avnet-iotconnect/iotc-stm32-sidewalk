"""
Unified /IOTCONNECT decoder for STM32 Sidewalk demos on the WBA55 platform.

Built for a single stacked device that can run any combination of:
  - sid_ble / sid_demo standard tags  (temperature, gps_time, link_type,
    buttons, LEDs, OTA state, firmware version)
  - X-NUCLEO-IKS4A1 high-precision MEMS sensors + 6D orientation + Qvar
  - X-NUCLEO-GNSS1A1 (Teseo-LIV3F) GNSS position + MCU temp + counter

Auto-detects the wire format from the first byte after AWS hex-ASCII unwrap:

  first byte 0x40 - 0x5F  -> sid_demo TLV
                             msg_desc + (size_type<<6|tag) entries
                             values little-endian
                             tags 0x06 / 0x07 / 0x0C / 0x0E / 0x0F (sid_demo)
                                  0x20 - 0x29 (IKS4A1)
                                  0x2A - 0x31 (GNSS-over-sid_demo, see below)

  any other first byte  -> plain TLV (Teseo-style)
                           (tag, length, value) bytes
                           values big-endian, IEEE-754 floats for lat/lon/alt
                           tags 0x37 (MCU temp), 0x60 (GNSS pos), 0xC7 (counter)

The sid_demo path's GNSS tags (0x2A-0x31) are reserved for a future combined
firmware that emits IKS4A1 sensors AND GNSS in one sid_demo TLV stream. They
use signed integer encodings (lat/lon as deg x 1e7, altitude as cm) for
deterministic precision across the BLE link; the same dashboard fields
populate whether the data comes from the standalone Teseo firmware (plain
TLV path) or a future combined firmware (sid_demo path).

Output: a single flat dict whose keys are normalized so the same
/IOTCONNECT template attributes render data from either firmware.

/IOTCONNECT entry point:

    def dict_from_payload(base64_input: str, fport: int = None)
        -> {"payload": {...}}
"""

import base64
import json
import struct
from datetime import datetime, timezone


# ---------- sid_demo standard tags (sid_demo_types.h) ----------
SID_TAG_NUMBER_OF_BUTTONS                = 0x01
SID_TAG_NUMBER_OF_LEDS                   = 0x02
SID_TAG_BUTTON_PRESS_ACTION_NOTIFY       = 0x05
SID_TAG_TEMPERATURE_SENSOR_DATA_NOTIFY   = 0x06
SID_TAG_CURRENT_GPS_TIME_IN_SECONDS      = 0x07
SID_TAG_TEMP_SENSOR_AVAILABLE_UNIT       = 0x0B
SID_TAG_LINK_TYPE                        = 0x0C
SID_TAG_OTA_SUPPORTED                    = 0x0E
SID_TAG_OTA_FIRMWARE_VERSION             = 0x0F
SID_TAG_OTA_TRIGGER_NOTIFY               = 0x10
SID_TAG_OTA_STATS                        = 0x11
SID_TAG_OTA_COMPLETION_STATUS            = 0x12

# ---------- IKS4A1-specific tags (sid_demo TLV path, LE values) ----------
TAG_IKS4A1_VERSION       = 0x20
TAG_IKS4A1_SEQUENCE      = 0x21
TAG_IKS4A1_ACCEL         = 0x22
TAG_IKS4A1_GYRO          = 0x23
TAG_IKS4A1_TEMP_STTS22H  = 0x24
TAG_IKS4A1_TEMP_SHT40    = 0x25
TAG_IKS4A1_HUMIDITY      = 0x26
TAG_IKS4A1_PRESSURE      = 0x27
TAG_IKS4A1_ORIENTATION   = 0x28
TAG_IKS4A1_QVAR_RAW      = 0x29

# ---------- GNSS-over-sid_demo tags (forward-compat for combined firmware) ----------
TAG_GNSS_LAT_DEG_X1E7    = 0x2A   # i32 LE, deg * 1e7
TAG_GNSS_LON_DEG_X1E7    = 0x2B   # i32 LE, deg * 1e7
TAG_GNSS_ALT_CM          = 0x2C   # i32 LE, cm (altitude)
TAG_GNSS_HACC_CM         = 0x2D   # u16 LE, cm (horizontal accuracy)
TAG_GNSS_VACC_CM         = 0x2E   # u16 LE, cm (vertical accuracy)
TAG_GNSS_FIX_QUALITY     = 0x2F   # u8 (0=none, 1=2D, 2=3D, 3=DGPS, 4=RTK)
TAG_GNSS_NUM_SATS        = 0x30   # u8 (satellites in use)
TAG_GNSS_TIME_EPOCH      = 0x31   # u32 LE (Unix epoch seconds)

# ---------- Standalone-Teseo plain TLV tags (BE values) ----------
TAG_TESEO_MCU_TEMP   = 0x37
TAG_TESEO_GNSS_POS   = 0x60
TAG_TESEO_COUNTER    = 0xC7


LINK_TYPE_MAP = {1: "BLE", 2: "FSK", 3: "LORA"}

ORIENT_MAP = {
    0: "unknown",
    1: "landscape_right",   # +X face up
    2: "landscape_left",    # -X face up
    3: "portrait_up",       # +Y face up
    4: "portrait_down",     # -Y face up
    5: "face_up",           # +Z face up
    6: "face_down",         # -Z face up
}

FIX_MAP = {0: "no_fix", 1: "2d", 2: "3d", 3: "dgps", 4: "rtk"}


# ====== sid_demo TLV path =============================================

def _read_sid_tlv(data, offset):
    if offset >= len(data):
        raise ValueError("sid_demo TLV: unexpected end of buffer")
    header = data[offset]
    offset += 1
    size_type = (header >> 6) & 0x3
    tag       = header & 0x3F
    size_len  = {0: 1, 1: 2, 2: 4}.get(size_type)
    if size_len is None:
        raise ValueError("sid_demo TLV: invalid size type")
    if offset + size_len > len(data):
        raise ValueError("sid_demo TLV: truncated length")
    length = int.from_bytes(data[offset:offset + size_len], "little")
    offset += size_len
    if offset + length > len(data):
        raise ValueError("sid_demo TLV: truncated value")
    value = data[offset:offset + length]
    offset += length
    return tag, length, value, offset


def _i16_le(b):
    v = int.from_bytes(b, "little", signed=False)
    if v >= 0x8000:
        v -= 0x10000
    return v


def _parse_sid_demo(data):
    msg_desc       = data[0]
    status_hdr_ind = (msg_desc >> 7) & 0x1
    opc            = (msg_desc >> 5) & 0x3
    cmd_class      = (msg_desc >> 3) & 0x3
    cmd_id         =  msg_desc       & 0x7

    offset = 1
    if status_hdr_ind:
        if len(data) < 2:
            raise ValueError("sid_demo: missing status code byte")
        offset = 2

    payload = data[offset:]
    result = {
        "id": f"{opc}-{cmd_class}-{cmd_id}",
        "Sequence": 0,
        "Sinewave": 0,
        "version": 0,
        "payload_size": len(data),
        "source": "sid_demo",
    }

    tlv_off = 0
    while tlv_off < len(payload):
        tag, length, value, tlv_off = _read_sid_tlv(payload, tlv_off)

        # --- sid_demo standard ---
        if   tag == SID_TAG_TEMPERATURE_SENSOR_DATA_NOTIFY and len(value) >= 2:
            t = _i16_le(value[0:2])
            result["sensor_data"] = int(t)
            result["Temperature"] = float(t)
        elif tag == SID_TAG_CURRENT_GPS_TIME_IN_SECONDS and len(value) >= 4:
            result["gps_time"] = int.from_bytes(value[0:4], "little", signed=False)
        elif tag == SID_TAG_LINK_TYPE and len(value) >= 1:
            result["link_type"] = LINK_TYPE_MAP.get(value[0], f"LINK_{value[0]}")
        elif tag == SID_TAG_OTA_SUPPORTED and len(value) >= 1:
            result["ota_supported"] = int(value[0])
        elif tag == SID_TAG_OTA_FIRMWARE_VERSION and len(value) >= 8:
            major = int.from_bytes(value[0:2], "little")
            minor = int.from_bytes(value[2:4], "little")
            patch = int.from_bytes(value[4:6], "little")
            build = int.from_bytes(value[6:8], "little")
            result["fw_version"] = f"{major}.{minor}.{patch}-{build}"
        elif tag == SID_TAG_BUTTON_PRESS_ACTION_NOTIFY and value:
            result["button_pressed"] = ",".join(str(b) for b in value)

        # --- IKS4A1 ---
        elif tag == TAG_IKS4A1_VERSION and len(value) >= 1:
            result["version"] = int(value[0])
        elif tag == TAG_IKS4A1_SEQUENCE and len(value) >= 1:
            result["Sequence"] = int(value[0])
        elif tag == TAG_IKS4A1_ACCEL and len(value) >= 6:
            ax = _i16_le(value[0:2]); ay = _i16_le(value[2:4]); az = _i16_le(value[4:6])
            result["acc_x_g"] = round(ax / 1000.0, 3)
            result["acc_y_g"] = round(ay / 1000.0, 3)
            result["acc_z_g"] = round(az / 1000.0, 3)
        elif tag == TAG_IKS4A1_GYRO and len(value) >= 6:
            gx = _i16_le(value[0:2]); gy = _i16_le(value[2:4]); gz = _i16_le(value[4:6])
            result["gyr_x_dps"] = round(gx / 10.0, 1)
            result["gyr_y_dps"] = round(gy / 10.0, 1)
            result["gyr_z_dps"] = round(gz / 10.0, 1)
        elif tag == TAG_IKS4A1_TEMP_STTS22H and len(value) >= 2:
            result["temp_stts22h_c"] = round(_i16_le(value[0:2]) / 100.0, 2)
        elif tag == TAG_IKS4A1_TEMP_SHT40 and len(value) >= 2:
            result["temp_sht40_c"] = round(_i16_le(value[0:2]) / 100.0, 2)
        elif tag == TAG_IKS4A1_HUMIDITY and len(value) >= 2:
            rh = int.from_bytes(value[0:2], "little", signed=False)
            result["humidity_sht40_pct"] = round(rh / 100.0, 2)
        elif tag == TAG_IKS4A1_PRESSURE and len(value) >= 4:
            p = int.from_bytes(value[0:4], "little", signed=False)
            result["pressure_hpa"] = round(p / 100.0, 2)
        elif tag == TAG_IKS4A1_ORIENTATION and len(value) >= 1:
            result["orientation"] = ORIENT_MAP.get(int(value[0]), f"orient_{int(value[0])}")
        elif tag == TAG_IKS4A1_QVAR_RAW and len(value) >= 2:
            result["qvar"] = _i16_le(value[0:2])

        # --- GNSS over sid_demo (combined firmware) ---
        elif tag == TAG_GNSS_LAT_DEG_X1E7 and len(value) >= 4:
            lat = int.from_bytes(value[0:4], "little", signed=True)
            result["latitude"] = round(lat / 1e7, 7)
        elif tag == TAG_GNSS_LON_DEG_X1E7 and len(value) >= 4:
            lon = int.from_bytes(value[0:4], "little", signed=True)
            result["longitude"] = round(lon / 1e7, 7)
        elif tag == TAG_GNSS_ALT_CM and len(value) >= 4:
            alt_cm = int.from_bytes(value[0:4], "little", signed=True)
            result["altitude_m"] = round(alt_cm / 100.0, 2)
        elif tag == TAG_GNSS_HACC_CM and len(value) >= 2:
            result["horizontal_accuracy_m"] = round(int.from_bytes(value[0:2], "little") / 100.0, 2)
        elif tag == TAG_GNSS_VACC_CM and len(value) >= 2:
            result["vertical_accuracy_m"] = round(int.from_bytes(value[0:2], "little") / 100.0, 2)
        elif tag == TAG_GNSS_FIX_QUALITY and len(value) >= 1:
            result["fix_quality"] = FIX_MAP.get(int(value[0]), f"fix_{int(value[0])}")
        elif tag == TAG_GNSS_NUM_SATS and len(value) >= 1:
            result["num_sats"] = int(value[0])
        elif tag == TAG_GNSS_TIME_EPOCH and len(value) >= 4:
            ts = int.from_bytes(value[0:4], "little", signed=False)
            result["position_time_epoch"] = ts
            result["position_time"] = datetime.fromtimestamp(ts, timezone.utc).isoformat()

        # Unknown tags silently skipped (sid_demo convention).

    return result


# ====== Plain-TLV path (Teseo standalone firmware) ====================

def _read_plain_tlv(data, offset):
    if offset + 2 > len(data):
        raise ValueError("plain TLV: truncated header")
    tag    = data[offset]
    length = data[offset + 1]
    offset += 2
    if offset + length > len(data):
        raise ValueError("plain TLV: truncated value")
    value = data[offset:offset + length]
    offset += length
    return tag, length, value, offset


def _parse_teseo_gnss_position(value):
    if len(value) < 24:
        raise ValueError("Teseo GNSS position payload too short")
    ts_epoch  = int.from_bytes(value[0:4], "big", signed=False)
    latitude  = struct.unpack(">f", value[4:8])[0]
    longitude = struct.unpack(">f", value[8:12])[0]
    elevation = struct.unpack(">f", value[12:16])[0]
    h_acc     = struct.unpack(">f", value[16:20])[0]
    v_acc     = struct.unpack(">f", value[20:24])[0]
    return ts_epoch, latitude, longitude, elevation, h_acc, v_acc


def _parse_teseo(data):
    result = {
        "id": "teseo",
        "payload_size": len(data),
        "source": "teseo",
    }
    offset = 0
    while offset < len(data):
        tag, length, value, offset = _read_plain_tlv(data, offset)
        if tag == TAG_TESEO_GNSS_POS:
            ts, lat, lon, elev, h, v = _parse_teseo_gnss_position(value)
            result["position_time_epoch"] = ts
            result["position_time"]       = datetime.fromtimestamp(ts, timezone.utc).isoformat()
            result["latitude"]            = lat
            result["longitude"]           = lon
            result["altitude_m"]          = elev
            result["horizontal_accuracy_m"] = h
            result["vertical_accuracy_m"]   = v
        elif tag == TAG_TESEO_MCU_TEMP and len(value) >= 2:
            result["mcu_temperature_c"] = int.from_bytes(value[0:2], "big", signed=True)
        elif tag == TAG_TESEO_COUNTER and value:
            result["demo_counter"] = int.from_bytes(value, "big", signed=False)
    return result


# ====== AWS hex-ASCII unwrap ==========================================

def _maybe_unwrap_hex_string(data: bytes) -> bytes:
    """AWS IoT Wireless delivers Sidewalk payloads as base64(hex-ascii(raw)),
       so a single base64 decode lands at an ASCII hex string. If the bytes
       are even-length and all hex characters, decode again via fromhex().
       Real sid_demo and Teseo payloads contain non-hex bytes (length fields,
       raw float32s, etc.) so the heuristic is safe."""
    if len(data) < 2 or len(data) % 2 != 0:
        return data
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return data
    if not all(c in "0123456789abcdefABCDEF" for c in text):
        return data
    return bytes.fromhex(text)


# ====== Public entry point ============================================

def dict_from_payload(base64_input: str, fport: int = None):
    try:
        data = base64.b64decode(base64_input)
    except Exception as e:
        raise ValueError(f"Invalid base64 input: {e}")

    data = _maybe_unwrap_hex_string(data)
    if not data:
        raise ValueError("Decoded data is empty.")

    first = data[0]
    if 0x40 <= first <= 0x5F:
        # sid_demo NOTIFY (0x40 = capability, 0x41 = action, etc.)
        return {"payload": _parse_sid_demo(data)}
    # Anything else is treated as plain-TLV (Teseo standalone firmware).
    return {"payload": _parse_teseo(data)}


# ====== Local self-test ===============================================

if __name__ == "__main__":
    def i16le(v): v &= 0xFFFF; return bytes([v & 0xFF, (v >> 8) & 0xFF])
    def u16le(v): return bytes([v & 0xFF, (v >> 8) & 0xFF])
    def u32le(v): return bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF])
    def i32le(v):
        v &= 0xFFFFFFFF
        return bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF])
    def stlv1(t, v): return bytes([t, 1, v & 0xFF])
    def stlv2(t, v): return bytes([t, 2]) + i16le(v)
    def stlv2u(t, v): return bytes([t, 2]) + u16le(v)
    def stlv4(t, v): return bytes([t, 4]) + u32le(v)
    def stlv4i(t, v): return bytes([t, 4]) + i32le(v)
    def stlv6(t, *vs): return bytes([t, 6]) + b"".join(i16le(x) for x in vs)
    def pltlv(t, value_bytes): return bytes([t, len(value_bytes)]) + value_bytes

    # --- sid_demo action frame with IKS4A1 sensors + GNSS-over-sid_demo ---
    sid_action = (
        bytes([0x41])  # msg_desc: NOTIFY DEMO_APP ACTION
        + stlv2 (SID_TAG_TEMPERATURE_SENSOR_DATA_NOTIFY, 25)
        + stlv4 (SID_TAG_CURRENT_GPS_TIME_IN_SECONDS, 1717372800)
        + stlv1 (SID_TAG_LINK_TYPE, 1)
        + stlv1 (TAG_IKS4A1_VERSION, 1)
        + stlv1 (TAG_IKS4A1_SEQUENCE, 42)
        + stlv6 (TAG_IKS4A1_ACCEL, 5, -2, 1003)
        + stlv6 (TAG_IKS4A1_GYRO, 0, 0, 0)
        + stlv2 (TAG_IKS4A1_TEMP_STTS22H, 2550)
        + stlv2 (TAG_IKS4A1_TEMP_SHT40, 2555)
        + stlv2u(TAG_IKS4A1_HUMIDITY, 5043)
        + stlv4 (TAG_IKS4A1_PRESSURE, 99341)
        + stlv1 (TAG_IKS4A1_ORIENTATION, 5)        # face_up
        + stlv2 (TAG_IKS4A1_QVAR_RAW, 1234)
        + stlv4i(TAG_GNSS_LAT_DEG_X1E7,  389807500)   # 38.9807500
        + stlv4i(TAG_GNSS_LON_DEG_X1E7, -770368500)   # -77.0368500
        + stlv4i(TAG_GNSS_ALT_CM, 4500)               # 45 m
        + stlv2u(TAG_GNSS_HACC_CM, 250)               # 2.5 m
        + stlv2u(TAG_GNSS_VACC_CM, 380)               # 3.8 m
        + stlv1 (TAG_GNSS_FIX_QUALITY, 2)             # 3D
        + stlv1 (TAG_GNSS_NUM_SATS, 9)
        + stlv4 (TAG_GNSS_TIME_EPOCH, 1717372805)
    )

    # --- Teseo standalone-firmware payload ---
    teseo_gnss_value = (
        u32le(0).__class__()  # placeholder; build BE below
    )
    teseo_gnss = (
        (1717372800).to_bytes(4, "big")              # ts_epoch
        + struct.pack(">f", 38.98075)                # lat
        + struct.pack(">f", -77.03685)               # lon
        + struct.pack(">f", 45.0)                    # elevation m
        + struct.pack(">f", 2.5)                     # h_acc m
        + struct.pack(">f", 3.8)                     # v_acc m
    )
    teseo_payload = (
          pltlv(TAG_TESEO_COUNTER, (7).to_bytes(2, "big"))
        + pltlv(TAG_TESEO_MCU_TEMP, (28).to_bytes(2, "big"))
        + pltlv(TAG_TESEO_GNSS_POS, teseo_gnss)
    )

    def run(label, raw):
        b64_raw = base64.b64encode(raw).decode()
        b64_hex = base64.b64encode(raw.hex().encode()).decode()
        print(f"\n=== {label}  ({len(raw)} bytes) ===")
        for kind, b64 in [("raw    ", b64_raw), ("AWS hex", b64_hex)]:
            try:
                out = dict_from_payload(b64)["payload"]
                print(f"  [{kind}] source={out.get('source')}  keys={len(out)}  "
                      f"id={out.get('id')}")
                print("           " + json.dumps(out, indent=2).replace("\n", "\n           "))
            except Exception as e:
                print(f"  [{kind}] EXCEPTION {e!r}")

    run("sid_demo action + IKS4A1 + GNSS-over-sid_demo", sid_action)
    run("Teseo standalone (plain TLV)",                  teseo_payload)
