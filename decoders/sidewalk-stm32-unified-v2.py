"""
Unified /IOTCONNECT decoder for STM32 Sidewalk demos on the WBA55 platform.

v2: adds FUOTA/OTA uplink decoding - download progress (percent / bytes) and
completion status reported by the sid_sbdt_demo application (tags 0x10-0x13).

IMPORTANT - corrected sid_demo TLV wire format (verified against real device
captures, see __main__): each entry header byte is (size_type<<6 | tag), where
size_type gives the VALUE size directly - 0->1 byte, 1->2 bytes, 2->4 bytes,
3->variable (next byte is the length). Multi-byte integers are BIG-endian. v1
mis-modelled this (treated size_type as a length-field size, little-endian) and
could not decode OTA/FUOTA frames at all.

NOTE: the OTA + capability + link_type paths are verified against real captures.
The IKS4A1 / GNSS sensor field handlers are inherited from v1 and still use
little-endian; they should be re-validated against real sensor captures before use.

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
SID_TAG_OTA_FILE_ID                      = 0x13
SID_TAG_APP_VERSION                      = 0x14   # application version (SID_APP_PROJECT_*)

# FUOTA completion-status codes (SID_DEMO_OTA_COMPLETION_STATUS_*)
OTA_STATUS_MAP = {0: "INITIAL", 1: "SUCCESS", 2: "FAILED"}

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
    # Wire format (verified against real device captures, see __main__):
    #   header byte = (size_type << 6) | tag
    #   size_type encodes the VALUE size (NOT a length-field size):
    #     0 -> 1-byte value,  1 -> 2-byte value,  2 -> 4-byte value,
    #     3 -> variable: the next byte is the length, then that many value bytes.
    #   multi-byte integer values are big-endian.
    header = data[offset]
    offset += 1
    size_type = (header >> 6) & 0x3
    tag       = header & 0x3F
    if size_type == 0:
        length = 1
    elif size_type == 1:
        length = 2
    elif size_type == 2:
        length = 4
    else:  # size_type == 3 -> explicit 1-byte length prefix, then variable value
        if offset >= len(data):
            raise ValueError("sid_demo TLV: truncated length")
        length = data[offset]
        offset += 1
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
            major = int.from_bytes(value[0:2], "big")
            minor = int.from_bytes(value[2:4], "big")
            patch = int.from_bytes(value[4:6], "big")
            build = int.from_bytes(value[6:8], "big")
            result["fw_version"] = f"{major}.{minor}.{patch}-{build}"
        elif tag == SID_TAG_APP_VERSION and len(value) >= 6:
            major = int.from_bytes(value[0:2], "big")
            minor = int.from_bytes(value[2:4], "big")
            patch = int.from_bytes(value[4:6], "big")
            result["app_version"] = f"{major}.{minor}.{patch}"
        # --- FUOTA / OTA uplink progress + status (sid_sbdt_demo) ---
        elif tag == SID_TAG_OTA_TRIGGER_NOTIFY and len(value) >= 1:
            result["ota_trigger"] = int(value[0])
        elif tag == SID_TAG_OTA_STATS and len(value) >= 9:
            # value = percent(1) + completed_bytes(4 BE) + total_bytes(4 BE)
            result["ota_percent"] = int(value[0])
            result["ota_completed_bytes"] = int.from_bytes(value[1:5], "big", signed=False)
            result["ota_total_bytes"] = int.from_bytes(value[5:9], "big", signed=False)
        elif tag == SID_TAG_OTA_COMPLETION_STATUS and len(value) >= 1:
            result["ota_status_code"] = int(value[0])
            result["ota_status"] = OTA_STATUS_MAP.get(int(value[0]), f"STATUS_{value[0]}")
        elif tag == SID_TAG_OTA_FILE_ID and len(value) >= 4:
            result["ota_file_id"] = int.from_bytes(value[0:4], "big", signed=False)
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
    # ---------------------------------------------------------------------
    # Real FUOTA progress uplinks captured from the SBDT-demo device
    # (WirelessDeviceId 95fe9e17-4606-4b49-9013-a9e8f05998d2), taken verbatim
    # from the IoTCONNECT MQTT subscription. PayloadData = base64(hex-ascii(raw)),
    # which dict_from_payload() unwraps automatically.
    #
    # Each entry: (PayloadData, expected percent, completed_bytes, total_bytes)
    # Values cross-checked against the device's own "Notify: [pct:done:total]" log.
    # ---------------------------------------------------------------------
    OTA_PROGRESS_SAMPLES = [
        ("NDFkMTA5MDAwMDAwMDQwMDAwMDYxNjI0OTMwMDAwMDAwMDBjMDE=", 0, 1024,  398884),
        ("NDFkMTA5MDAwMDAwMDgwMDAwMDYxNjI0OTMwMDAwMDAwMDBjMDE=", 0, 2048,  398884),
        ("NDFkMTA5MDEwMDAwMTAwMDAwMDYxNjI0OTMwMDAwMDAwMDBjMDE=", 1, 4096,  398884),
        ("NDFkMTA5MDEwMDAwMTQwMDAwMDYxNjI0OTMwMDAwMDAwMDBjMDE=", 1, 5120,  398884),
    ]

    def _ota_fields(out):
        return {k: out[k] for k in out
                if k.startswith("ota") or k in ("id", "link_type")}

    print("=== FUOTA progress uplinks (real device captures) ===")
    all_ok = True
    for b64, exp_pct, exp_comp, exp_tot in OTA_PROGRESS_SAMPLES:
        out = dict_from_payload(b64)["payload"]
        ok = (out.get("ota_percent") == exp_pct
              and out.get("ota_completed_bytes") == exp_comp
              and out.get("ota_total_bytes") == exp_tot)
        all_ok = all_ok and ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {b64}")
        print(f"         -> {json.dumps(_ota_fields(out))}")
        if not ok:
            print(f"         !! expected pct={exp_pct} completed={exp_comp} total={exp_tot}")

    # Synthetic completion-status frame (no real capture available yet):
    #   msg_desc=0x41, OTA_COMPLETION_STATUS(0x12)=SUCCESS(1), FILE_ID(0x13)=0, LINK_TYPE(0x0C)=1
    #   headers use the real encoding: 0x12 (size_type 0, 1-byte val), 0x93 (size_type 2, 4-byte val), 0x0C
    comp_raw = bytes([0x41, 0x12, 0x01, 0x93, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x01])
    comp_out = dict_from_payload(base64.b64encode(comp_raw).decode())["payload"]
    print("\n=== FUOTA completion status (synthetic) ===")
    print(f"  -> {json.dumps(_ota_fields(comp_out))}")
    all_ok = all_ok and comp_out.get("ota_status") == "SUCCESS"

    print("\nRESULT:", "ALL PASS" if all_ok else "SOME FAILED")
