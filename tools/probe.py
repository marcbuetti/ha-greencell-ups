"""Read-only probe of a GC UPS App - dumps what the integration will see.

Credentials come from the environment so no password ends up in shell history:

    GCUPS_HOST=10.25.14.4:8080 GCUPS_PASSWORD=... python tools/probe.py
    # or: set -a && . ./nexus.env && set +a && GCUPS_HOST=$UPS_URL GCUPS_PASSWORD=$UPS_AUTH ...

Never sends a command.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

import aiohttp

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "greencell_ups"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"gcups_{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


api = _load("api")
model = _load("model")


async def main() -> None:
    host = os.environ.get("GCUPS_HOST") or (sys.argv[1] if len(sys.argv) > 1 else None)
    password = os.environ.get("GCUPS_PASSWORD")
    if not host or not password:
        sys.exit("set GCUPS_HOST and GCUPS_PASSWORD")
    async with aiohttp.ClientSession() as session:
        client = api.GCUPSApi(session, host, password)
        print("status:", await client.status())
        out = {"current_parameters": await client.current_parameters()}
        for name, call in (
            ("nominal_parameters", client.nominal_parameters),
            ("specification", client.specification),
            ("device_data", client.device_data),
        ):
            try:
                out[name] = await call()
            except api.GCUPSError as err:
                out[name] = f"ERROR {err}"
        print(json.dumps(out, indent=2, ensure_ascii=False))
        d = model.UPSData(
            current=out["current_parameters"],
            nominal=out["nominal_parameters"]
            if isinstance(out["nominal_parameters"], dict)
            else {},
            spec=out["specification"] if isinstance(out["specification"], dict) else {},
            info=out["device_data"] if isinstance(out["device_data"], dict) else {},
        )
        print("\nderived:")
        for key in (
            "status", "connected", "battery_level", "battery_voltage", "input_voltage",
            "output_voltage", "input_frequency", "load", "output_power", "temperature",
            "utility_fail", "charging", "model", "manufacturer", "firmware",
        ):  # fmt: skip
            print(f"  {key:16} {getattr(d, key)}")


asyncio.run(main())
