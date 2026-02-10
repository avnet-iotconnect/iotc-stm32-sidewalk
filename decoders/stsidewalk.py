import base64
import json
import os

# Sidewalk demo TLV tags (apps/common/sid_demo_parser/include/sid_demo_types.h)
TAG_NUMBER_OF_BUTTONS = 0x01
TAG_NUMBER_OF_LEDS = 0x02
TAG_LED_ON_ACTION_REQ = 0x03
TAG_LED_OFF_ACTION_REQ = 0x04
TAG_BUTTON_PRESS_ACTION_NOTIFY = 0x05
TAG_TEMPERATURE_SENSOR_DATA_NOTIFY = 0x06
TAG_CURRENT_GPS_TIME_IN_SECONDS = 0x07
TAG_DL_LATENCY_IN_SECONDS = 0x08
TAG_LED_ON_RESP = 0x09
TAG_LED_OFF_RESP = 0x0A
TAG_TEMP_SENSOR_AVAILABLE_AND_UNIT_REPRESENTATION = 0x0B
TAG_LINK_TYPE = 0x0C
TAG_BUTTON_PRESSED_RESP = 0x0D
TAG_OTA_SUPPORTED = 0x0E
TAG_OTA_FIRMWARE_VERSION = 0x0F
TAG_OTA_TRIGGER_NOTIFY = 0x10
TAG_OTA_STATS = 0x11
TAG_OTA_COMPLETION_STATUS = 0x12
TAG_OTA_FILE_ID = 0x13

LINK_TYPE_MAP = {
    1: "BLE",
    2: "FSK",
    3: "LORA",
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


def _list_to_csv(values):
    if values is None:
        return ""
    return ",".join(str(v) for v in values)


def _parse_demo_msg(data, debug=False):
    if len(data) < 1:
        raise ValueError("Decoded data must be at least 1 byte.")

    msg_desc = data[0]
    status_hdr_ind = (msg_desc >> 7) & 0x1
    opc = (msg_desc >> 5) & 0x3
    cmd_class = (msg_desc >> 3) & 0x3
    cmd_id = msg_desc & 0x7

    offset = 1
    status_code = None
    if status_hdr_ind:
        if len(data) < 2:
            raise ValueError("Decoded data missing status code.")
        status_code = data[1]
        offset = 2

    payload = data[offset:]

    # Provide defaults for template-required fields so IOTCONNECT doesn't drop the record
    result = {
        "id": f"{opc}-{cmd_class}-{cmd_id}",
        "Sequence": int(cmd_id),
        "Sinewave": 0,
    }

    tlv_dump = []
    unknown_tags = []

    # Parse TLV payload
    tlv_offset = 0
    while tlv_offset < len(payload):
        tag, length, value, tlv_offset = _read_tlv(payload, tlv_offset)

        if debug:
            tlv_dump.append(
                {
                    "tag": tag,
                    "length": length,
                    "value_hex": value.hex(),
                }
            )

        if tag == TAG_TEMPERATURE_SENSOR_DATA_NOTIFY:
            temp_raw = int.from_bytes(value[:2], byteorder="little", signed=False)
            # Temperature is int16 degrees C in sid_pal_temperature_get()
            if temp_raw >= 0x8000:
                temp_raw -= 0x10000
            result["sensor_data"] = int(temp_raw)
            result["Temperature"] = float(temp_raw)
        elif tag == TAG_CURRENT_GPS_TIME_IN_SECONDS:
            result["gps_time"] = int.from_bytes(value[:4], byteorder="little")
        elif tag == TAG_LINK_TYPE:
            link_id = value[0] if value else 0
            result["link_type"] = LINK_TYPE_MAP.get(link_id, f"LINK_{link_id}")
        elif tag == TAG_BUTTON_PRESS_ACTION_NOTIFY:
            # button ids array
            result["button_pressed"] = _list_to_csv(list(value))
        elif tag == TAG_OTA_FIRMWARE_VERSION:
            if len(value) >= 8:
                major = int.from_bytes(value[0:2], "little")
                minor = int.from_bytes(value[2:4], "little")
                patch = int.from_bytes(value[4:6], "little")
                build = int.from_bytes(value[6:8], "little")
                result["Version"] = f"{major}.{minor}.{patch}-{build}"
        elif tag == TAG_OTA_STATS:
            if len(value) >= 9:
                percent = value[0]
                completed = int.from_bytes(value[1:5], "little")
                total = int.from_bytes(value[5:9], "little")
                result["ota_percent"] = int(percent)
                result["ota_completed_bytes"] = int(completed)
                result["ota_total_bytes"] = int(total)
        elif tag == TAG_OTA_COMPLETION_STATUS:
            result["ota_status"] = int(value[0]) if value else 0
        elif tag == TAG_OTA_FILE_ID:
            result["ota_file_id"] = int.from_bytes(value[:4], "little")
        elif tag == TAG_NUMBER_OF_BUTTONS:
            result["num_buttons"] = int(length)
            result["button_ids"] = _list_to_csv(list(value))
        elif tag == TAG_NUMBER_OF_LEDS:
            result["num_leds"] = int(length)
            result["led_ids"] = _list_to_csv(list(value))
        elif tag == TAG_LED_ON_ACTION_REQ:
            result["led_on_req"] = _list_to_csv(list(value))
        elif tag == TAG_LED_OFF_ACTION_REQ:
            result["led_off_req"] = _list_to_csv(list(value))
        elif tag == TAG_LED_ON_RESP:
            result["led_on_resp"] = _list_to_csv(list(value))
        elif tag == TAG_LED_OFF_RESP:
            result["led_off_resp"] = _list_to_csv(list(value))
        elif tag == TAG_DL_LATENCY_IN_SECONDS:
            result["downlink_latency_s"] = int.from_bytes(value[:4], "little")
        elif tag == TAG_TEMP_SENSOR_AVAILABLE_AND_UNIT_REPRESENTATION:
            result["temp_sensor_units"] = int(value[0]) if value else 0
        elif tag == TAG_OTA_SUPPORTED:
            result["ota_supported"] = int(value[0]) if value else 0
        elif tag == TAG_OTA_TRIGGER_NOTIFY:
            result["ota_trigger"] = int(value[0]) if value else 0
        elif tag == TAG_BUTTON_PRESSED_RESP:
            result["button_pressed_resp"] = _list_to_csv(list(value))
        else:
            unknown_tags.append(tag)

    if debug:
        result["_raw_hex"] = data.hex()
        result["_tlv_dump"] = tlv_dump
        if unknown_tags:
            result["_unknown_tags"] = unknown_tags

    return result


def dict_from_payload(base64_input: str, fport: int = None):
    debug = os.getenv("SID_DECODER_DEBUG", "").lower() in ("1", "true", "yes", "on")
    try:
        data = base64.b64decode(base64_input)
    except Exception as e:
        raise ValueError(f"Invalid base64 input: {e}")

    payload = _parse_demo_msg(data, debug=debug)
    return {"payload": payload}

# Example usage
if __name__ == "__main__":

    value_range = [
        "OTM=",
        "YzY=",
        "Yzc=",
        "Yzg=",
        "Yzk="
    ]

    for base64_input in value_range:
        try:
            result = dict_from_payload(base64_input)
            print(f"Input: {base64_input}\nOutput:\n{json.dumps(result, indent=2)}\n")
        except ValueError as err:
            print(f"Input: {base64_input}\nError: {err}\n")
