"""
IKS4A1 downlink JSON -> opcode bytes translator.

This is the cloud-side counterpart to sidewalk_iks4a1.py (the uplink decoder).
It mirrors the role played by SidewalkDownlinkLambda in
aws-iot-core-for-amazon-sidewalk-sample-app: a thin function that takes the
JSON command emitted by the dashboard / device template and returns the raw
byte payload to send via iotwireless.send_data_to_wireless_device.

JSON commands (from sidewalk_iks4a1_template.json):
    {"command": "IKS4A1_LED_ON"}
    {"command": "IKS4A1_LED_OFF"}
    {"command": "IKS4A1_SET_INTERVAL", "interval_seconds": 300}

Wire format produced (matches commands_iks4a1.h):
    LED_ON       -> 01
    LED_OFF      -> 02
    SET_INTERVAL -> 10 <BE uint32 seconds>   (clamped 60..3600 device-side)

Deploy this as a Lambda behind /IOTCONNECT's downlink path, or call
encode_command() in-process from any glue code that owns
send_data_to_wireless_device.
"""
from __future__ import annotations

import base64
import json
import struct
from typing import Final


CMD_LED_ON: Final         = 0x01
CMD_LED_OFF: Final        = 0x02
CMD_SET_INTERVAL: Final   = 0x10

INTERVAL_MIN_S: Final = 60
INTERVAL_MAX_S: Final = 3600


class TranslateError(ValueError):
    pass


def encode_command(cmd: dict | str) -> bytes:
    """Translate a dashboard command (JSON string or dict) to wire bytes."""
    if isinstance(cmd, str):
        try:
            cmd = json.loads(cmd)
        except json.JSONDecodeError as exc:
            raise TranslateError(f"command is not valid JSON: {exc}") from exc

    if not isinstance(cmd, dict):
        raise TranslateError("command must be a JSON object")

    name = cmd.get("command")
    if not isinstance(name, str):
        raise TranslateError("missing string field 'command'")

    if name == "IKS4A1_LED_ON":
        return bytes([CMD_LED_ON])
    if name == "IKS4A1_LED_OFF":
        return bytes([CMD_LED_OFF])
    if name == "IKS4A1_SET_INTERVAL":
        secs = cmd.get("interval_seconds")
        if not isinstance(secs, int):
            raise TranslateError(
                "IKS4A1_SET_INTERVAL requires integer 'interval_seconds'"
            )
        secs = max(INTERVAL_MIN_S, min(INTERVAL_MAX_S, secs))
        return bytes([CMD_SET_INTERVAL]) + struct.pack(">I", secs)

    raise TranslateError(f"unknown command: {name!r}")


def lambda_handler(event, context=None):
    """
    AWS Lambda entrypoint. Expected event shape (mirrors AWS sample):
        {
            "wirelessDeviceId": "...",
            "command": "{\"command\": \"IKS4A1_LED_ON\"}"   # string or dict
        }

    Returns:
        {
            "wirelessDeviceId": "...",
            "payloadHex":   "01",
            "payloadBase64":"AQ=="
        }

    The caller (or this function, if you wire up boto3) then invokes
    iotwireless.send_data_to_wireless_device with PayloadData=payloadBase64.
    """
    if isinstance(event, str):
        event = json.loads(event)

    wid = event.get("wirelessDeviceId")
    payload = encode_command(event.get("command"))
    return {
        "wirelessDeviceId": wid,
        "payloadHex":   payload.hex(),
        "payloadBase64": base64.b64encode(payload).decode("ascii"),
    }


# Local self-test
if __name__ == "__main__":
    samples = [
        '{"command": "IKS4A1_LED_ON"}',
        '{"command": "IKS4A1_LED_OFF"}',
        '{"command": "IKS4A1_SET_INTERVAL", "interval_seconds": 300}',
        '{"command": "IKS4A1_SET_INTERVAL", "interval_seconds": 5}',     # clamps up
        '{"command": "IKS4A1_SET_INTERVAL", "interval_seconds": 99999}', # clamps down
    ]
    for s in samples:
        out = encode_command(s)
        print(f"{s}\n  -> hex={out.hex()}  b64={base64.b64encode(out).decode()}\n")
