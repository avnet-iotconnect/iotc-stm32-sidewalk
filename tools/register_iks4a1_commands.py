#!/usr/bin/env python3
"""
Register the WBA55 + IKS4A1 downlink bytes commands against an /IOTCONNECT
device template via the public REST API.

Endpoints used (see iotconnect-rest-api-uat-aws.pdf, WirelessDevice section):
    GET  /api/v2.1/device-template/datatype/{templateGuid}?hasBytesSupport=true
    GET  /api/v2.1/WirelessDevice/{templateGuid}/bytesCommandList
    POST /api/v2.1/WirelessDevice/{templateGuid}/bytesCommand

Usage:
    # Dry-run (default): prints exactly what would be POSTed and lists existing
    # bytes commands on the template. Does NOT modify anything.
    python3 register_iks4a1_commands.py \
        --base-url https://awspocdevice.iotconnect.io \
        --token "$IOTC_BEARER" \
        --template-guid <DEVICE_TEMPLATE_GUID>

    # Apply: actually POST the three commands.
    python3 register_iks4a1_commands.py ... --apply

The bearer token is obtained via POST /api/v1.1/auth/login (not implemented
here on purpose; this script never sees credentials). Pass the resulting token
in --token or via the IOTC_BEARER environment variable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import error, request


COMMANDS_FILE = Path(__file__).resolve().parent.parent / \
    "device-templates" / "sidewalk_iks4a1_bytes_commands.json"


def http(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"HTTP {exc.code} on {method} {url}\n{body_text}"
        ) from exc


def list_datatypes(base_url: str, token: str, template_guid: str) -> list[dict]:
    url = (
        f"{base_url.rstrip('/')}/api/v2.1/device-template/datatype/"
        f"{template_guid}?hasBytesSupport=true"
    )
    resp = http("GET", url, token)
    return resp.get("data", []) or []


def list_existing(base_url: str, token: str, template_guid: str) -> list[dict]:
    url = (
        f"{base_url.rstrip('/')}/api/v2.1/WirelessDevice/{template_guid}"
        f"/bytesCommandList"
    )
    resp = http("GET", url, token)
    return resp.get("data", []) or []


def add_bytes_command(
    base_url: str, token: str, template_guid: str, body: dict
) -> dict:
    url = (
        f"{base_url.rstrip('/')}/api/v2.1/WirelessDevice/{template_guid}"
        f"/bytesCommand"
    )
    return http("POST", url, token, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True,
                        help="Device service base URL, e.g. "
                             "https://awspocdevice.iotconnect.io")
    parser.add_argument("--template-guid", required=True,
                        help="Device template GUID created from "
                             "sidewalk_iks4a1_template.json")
    parser.add_argument("--token", default=os.environ.get("IOTC_BEARER", ""),
                        help="Bearer token from /api/v1.1/auth/login. May also "
                             "be passed via the IOTC_BEARER env var.")
    parser.add_argument("--commands-file", default=str(COMMANDS_FILE),
                        help="Path to sidewalk_iks4a1_bytes_commands.json")
    parser.add_argument("--apply", action="store_true",
                        help="Actually POST the commands. Default is dry-run.")
    args = parser.parse_args()

    if not args.token:
        print("ERROR: bearer token required (--token or IOTC_BEARER)",
              file=sys.stderr)
        return 2

    with open(args.commands_file, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    bodies = spec["bytesCommands"]

    print(f"Target: {args.base_url}  template={args.template_guid}")
    print(f"Mode  : {'APPLY (will POST)' if args.apply else 'dry-run'}\n")

    print("== Supported bytesCommandParameter dtName values "
          "(hasBytesSupport=true) ==")
    try:
        dtypes = list_datatypes(args.base_url, args.token, args.template_guid)
    except SystemExit as exc:
        print(f"  WARN: dtName lookup failed - {exc}")
        dtypes = []
    for dt in dtypes:
        name = dt.get("name") or dt.get("displayName") or dt
        print(f"  - {name}")
    if not dtypes:
        print("  (none returned; verify your token and template GUID)")
    print()

    print("== Existing bytes commands on this template ==")
    try:
        existing = list_existing(args.base_url, args.token, args.template_guid)
    except SystemExit as exc:
        print(f"  WARN: list failed - {exc}")
        existing = []
    existing_names = {c.get("name", c.get("commandName", "")) for c in existing}
    for c in existing:
        print(f"  - {c.get('name', c.get('commandName'))}  "
              f"command={c.get('command')}  guid={c.get('guid')}")
    if not existing:
        print("  (none)")
    print()

    print("== Bodies to register ==")
    for body in bodies:
        print(json.dumps(body, indent=2))

    if not args.apply:
        print("\nDry-run complete. Re-run with --apply to POST these commands.")
        return 0

    print("\n== Posting ==")
    for body in bodies:
        name = body["commandName"]
        if name in existing_names:
            print(f"  - {name}: skipped (already present)")
            continue
        try:
            resp = add_bytes_command(
                args.base_url, args.token, args.template_guid, body
            )
        except SystemExit as exc:
            print(f"  - {name}: FAILED - {exc}")
            continue
        new_id = (resp.get("data") or [{}])[0].get("newId")
        print(f"  - {name}: created (newId={new_id})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
