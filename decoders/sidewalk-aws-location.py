"""
/IOTCONNECT decoder for the WBA55 Sidewalk **AWS IoT Core Device Location** demo
(template: sidewalk_aws-location_wba55_template.JSON, code "STswLOC").

WHAT THIS DECODES
-----------------
For BLE Sidewalk location the *device never knows its own coordinates*. AWS IoT
Core Device Location resolves them in the cloud from the proximity of the
opted-in Sidewalk gateway and emits a GeoJSON "Point" to the location
destination, e.g.:

    {
      "coordinates": [-96.6826, 33.0287, 0],     # GeoJSON order: [lon, lat, alt]
      "type": "Point",
      "WirelessDeviceId": "....",
      "properties": {
        "measurementType": "BLE",                # or "Wi-Fi" | "GNSS" | "UserInput"
        "horizontalAccuracy": 1500.0,
        "timestamp": "2026-06-18T14:08:30Z"
      }
    }

This decoder assumes that resolved-location record is what reaches the decoder
(fork "B" in the example README). It converts GeoJSON **[lon, lat]** order into
the /IOTCONNECT **[lat, lon]** `location` (LATLONG) convention -- matching how a
device sends location in /IOTCONNECT, e.g. "location":[33.0287,-96.6826].

>>> IMPORTANT: if your /IOTCONNECT "positioning capability" instead auto-fills
    the `location` attribute directly from AWS (fork "A"), you do NOT need this
    decoder. Paste one real raw record for this device so the input format can
    be locked before you submit for approval.

/IOTCONNECT signature (same as the working sidewalk-mems-tlv.py):
    def dict_from_payload(base64_input: str, fport: int = None) -> {"payload": {...}}
"""

import base64
import json


# GeoJSON spec orders coordinates as [longitude, latitude, altitude].
# /IOTCONNECT's LATLONG attribute expects [latitude, longitude].
def _coords_to_latlon(coordinates):
    """Return [lat, lon] from a GeoJSON [lon, lat, (alt)] coordinate array."""
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        raise ValueError("coordinates must be a [lon, lat] array")
    lon = float(coordinates[0])
    lat = float(coordinates[1])
    # Sanity guard: longitude is the only value that can legally exceed +/-90.
    # If the producer already handed us [lat, lon], abs(first) <= 90 and
    # abs(second) can be > 90 -- detect and correct that case so a mis-ordered
    # upstream doesn't silently put the pin in the ocean.
    if abs(lat) > 90.0 and abs(lon) <= 90.0:
        lat, lon = lon, lat
    return [round(lat, 7), round(lon, 7)]


def _parse_geojson(obj):
    """Extract the /IOTCONNECT fields from an AWS Device Location GeoJSON dict."""
    coordinates = obj.get("coordinates")
    if coordinates is None and isinstance(obj.get("geometry"), dict):
        # Some pipelines wrap the Point in a GeoJSON Feature.
        coordinates = obj["geometry"].get("coordinates")
    if coordinates is None:
        raise ValueError("no 'coordinates' field in location record")

    result = {"location": _coords_to_latlon(coordinates)}

    # Altitude (GeoJSON coordinates[2]) is optional and usually absent for BLE
    # gateway location (AWS omits it when there's no vertical accuracy). Emit it
    # only when present so the `alt` attribute stays empty rather than 0 on a
    # 2D fix.
    if len(coordinates) >= 3 and coordinates[2] is not None:
        try:
            result["alt"] = round(float(coordinates[2]), 2)
        except (TypeError, ValueError):
            pass

    # Optional metadata -- harmless if the template doesn't define these
    # attributes (/IOTCONNECT ignores unknown keys). Add matching attributes to
    # the template if you want them surfaced.
    props = obj.get("properties") or {}
    if "measurementType" in props:
        result["measurement_type"] = props["measurementType"]
    if "horizontalAccuracy" in props:
        try:
            result["h_accuracy_m"] = round(float(props["horizontalAccuracy"]), 2)
        except (TypeError, ValueError):
            pass
    if "timestamp" in props:
        result["fix_time"] = props["timestamp"]

    return result


def _decode_text(base64_input: str) -> str:
    """base64 -> text. AWS IoT Wireless sometimes wraps payloads as
    base64(hex_ascii); peel that layer if present so we still land on JSON."""
    raw = base64.b64decode(base64_input)
    text = raw.decode("utf-8", errors="strict") if _looks_utf8(raw) else None
    if text is not None and text.lstrip()[:1] in ("{", "["):
        return text
    # Try the hex-ascii unwrap (raw is "7b22..." style hex of the JSON bytes).
    try:
        as_ascii = raw.decode("ascii")
        if len(as_ascii) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in as_ascii):
            return bytes.fromhex(as_ascii).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        pass
    # Fall back to whatever we decoded first (may raise downstream -> clear error)
    return raw.decode("utf-8", errors="replace")


def _looks_utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def dict_from_payload(base64_input: str, fport: int = None):
    if not base64_input:
        raise ValueError("empty payload")

    text = _decode_text(base64_input)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "payload is not the expected AWS Device Location GeoJSON. "
            "If the positioning capability auto-fills `location`, this decoder "
            "is not needed; otherwise share a real raw record. "
            f"(json error: {e}; first 60 chars: {text[:60]!r})"
        )

    if not isinstance(obj, dict):
        raise ValueError("expected a GeoJSON object")

    return {"payload": _parse_geojson(obj)}


# Local self-test
if __name__ == "__main__":
    sample = {
        "coordinates": [-96.6826, 33.0287, 0],
        "type": "Point",
        "WirelessDeviceId": "a1b2c3d4-5e6f-7a8b-9c0d-ef1234abcd56",
        "properties": {
            "measurementType": "BLE",
            "horizontalAccuracy": 1500.0,
            "timestamp": "2026-06-18T14:08:30Z",
        },
    }
    b64 = base64.b64encode(json.dumps(sample).encode()).decode()
    print("input base64 :", b64)
    out = dict_from_payload(b64)
    print(json.dumps(out, indent=2))
    # Expect location == [33.0287, -96.6826]  (i.e. [lat, lon])
    assert out["payload"]["location"] == [33.0287, -96.6826], out
    print("OK: GeoJSON [lon,lat] -> /IOTCONNECT [lat,lon]")
