"""Tests for api.py and model.py against a fake GC UPS App (no Home Assistant needed).

Run:  python -m pytest tests
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "greencell_ups"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"gcups_{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


api = _load("api")
model = _load("model")

PASSWORD = "gcups123"

# Shape copied from CurrentParametersDefault in the app bundle, with real-looking values.
CURRENT_OK = {
    "inputVoltage": 231.5,
    "inputVoltageFault": 231.5,
    "outputVoltage": 231.0,
    "load": 12,
    "inputFrequency": 50.0,
    "batteryVoltage": 13.7,
    "temperature": -1,
    "utilityFail": False,
    "batteryLow": False,
    "bypassBoost": False,
    "failed": False,
    "offline": True,  # topology, NOT a fault
    "testInProgress": False,
    "shutdownActive": False,
    "beeperOn": True,
    "batteryLevel": 100,
    "active": True,
    "connected": True,
    "status": 0,
    "register": [],
    "issues": [],
    "errno": 0,
    "batteryVoltageHighNominal": 12.6,
}
# What the app serves when the UPS is unplugged from USB.
CURRENT_DISCONNECTED = {
    "inputVoltage": -1,
    "outputVoltage": -1,
    "load": -1,
    "batteryVoltage": -1,
    "utilityFail": True,
    "batteryLow": True,
    "failed": True,
    "offline": True,
    "shutdownActive": True,
    "batteryLevel": -1,
    "connected": False,
}
SPEC = {"id": "UPS04", "name": "UPS04", "power": 900, "capacity": 1500, "online": False}


class FakeApp:
    def __init__(self) -> None:
        self.tokens: set[str] = set()
        self.n = 0
        self.current = dict(CURRENT_OK)
        self.logins = 0
        self.commands: list[dict] = []

    def _authed(self, request: web.Request) -> bool:
        return request.headers.get("Authorization", "").removeprefix("Bearer ") in self.tokens

    async def status(self, request):
        return web.Response(text="1")

    async def login(self, request):
        body = await request.json()
        if set(body) != {"password"}:
            return web.Response(status=403)  # strict schema
        if body["password"] != PASSWORD:
            return web.Response(status=401)
        self.logins += 1
        self.n += 1
        token = f"a.b{self.n}.c"
        self.tokens.add(token)
        return web.json_response({"access_token": token, "expires_in": 3600}, status=201)

    async def current_h(self, request):
        if not self._authed(request):
            return web.Response(status=401)
        return web.json_response(self.current)

    async def spec(self, request):
        if not self._authed(request):
            return web.Response(status=401)
        return web.json_response(SPEC)

    async def commands_(self, request):
        if not self._authed(request):
            return web.Response(status=401)
        body = await request.json()
        self.commands.append(body)
        return web.Response(text="true")

    def app(self) -> web.Application:
        a = web.Application()
        a.router.add_get("/api/status", self.status)
        a.router.add_post("/api/login", self.login)
        a.router.add_get("/api/current_parameters", self.current_h)
        a.router.add_get("/api/device/specification", self.spec)
        a.router.add_post("/api/commands", self.commands_)
        return a


@pytest.fixture
async def server():
    fake = FakeApp()
    runner = web.AppRunner(fake.app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    async with aiohttp.ClientSession() as session:
        yield fake, session, f"127.0.0.1:{port}"
    await runner.cleanup()


def test_normalize_host():
    n = api.normalize_host
    assert n("10.0.0.5") == "http://10.0.0.5:8080"
    assert n("10.0.0.5:8085") == "http://10.0.0.5:8085"
    assert n("http://pc.local/") == "http://pc.local:8080"
    assert n("https://pc.local:9443") == "https://pc.local:9443"
    assert n("[fe80::1]") == "http://[fe80::1]:8080"
    assert n("[fe80::1]:81") == "http://[fe80::1]:81"


async def test_login_and_read(server):
    fake, session, host = server
    client = api.GCUPSApi(session, host, PASSWORD)
    assert await client.status() is True
    cur = await client.current_parameters()
    assert cur["batteryLevel"] == 100
    await client.current_parameters()
    assert fake.logins == 1  # token reused


async def test_wrong_password(server):
    _, session, host = server
    with pytest.raises(api.GCUPSAuthError):
        await api.GCUPSApi(session, host, "nope").current_parameters()


async def test_token_invalidated_relogin_once(server):
    fake, session, host = server
    client = api.GCUPSApi(session, host, PASSWORD)
    await client.current_parameters()
    fake.tokens.clear()  # app restart invalidates tokens silently
    assert (await client.current_parameters())["connected"] is True
    assert fake.logins == 2


async def test_unreachable():
    async with aiohttp.ClientSession() as session:
        client = api.GCUPSApi(session, "127.0.0.1:1", PASSWORD)
        with pytest.raises(api.GCUPSConnectionError):
            await client.status()


async def test_command_body(server):
    fake, session, host = server
    client = api.GCUPSApi(session, host, PASSWORD)
    await client.command("shortTestOrder")
    assert fake.commands == [{"action": "shortTestOrder", "args": {}}]
    with pytest.raises(ValueError):
        await client.command("getLoad")


def test_model_normal():
    d = model.UPSData(current=CURRENT_OK, nominal={"batteryVoltageHighNominal": 12.6}, spec=SPEC)
    assert d.status == model.STATUS_ONLINE
    assert d.temperature is None  # -1 = no probe
    assert d.battery_level == 100
    assert d.output_power == 108.0  # 12 % of 900 W
    assert d.charging is True  # 13.7 V > 12.6 V on mains
    assert d.model == "UPS04"
    assert d.manufacturer == "Green Cell"


def test_model_on_battery():
    cur = {**CURRENT_OK, "utilityFail": True, "batteryVoltage": 12.4, "inputVoltage": 0}
    d = model.UPSData(current=cur, spec=SPEC)
    assert d.status == model.STATUS_ON_BATTERY
    assert d.input_voltage == 0.0  # 0 V is a real value
    assert d.charging is None


def test_model_battery_low_beats_on_battery():
    d = model.UPSData(current={**CURRENT_OK, "utilityFail": True, "batteryLow": True})
    assert d.status == model.STATUS_BATTERY_LOW


def test_model_disconnected_is_not_an_alarm():
    d = model.UPSData(current=CURRENT_DISCONNECTED, spec=SPEC)
    assert d.status == model.STATUS_DISCONNECTED
    assert d.failed is None and d.utility_fail is None and d.battery_low is None
    assert d.battery_level is None and d.output_power is None


def test_model_snake_case_and_strings():
    cur = {"connected": "true", "battery_level": "87", "is_utility_fail": 0, "load": "5"}
    d = model.UPSData(current=cur)
    assert d.battery_level == 87.0
    assert d.utility_fail is False
    assert d.status == model.STATUS_ONLINE
