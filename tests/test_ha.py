"""Home Assistant level tests (needs pytest-homeassistant-custom-component)."""

from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.greencell_ups.const import CONF_ENABLE_CONTROLS, DOMAIN

from .test_api_model import CURRENT_DISCONNECTED, CURRENT_OK, SPEC

BASE = "http://10.0.0.20:8080/api"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _mock_app(aioclient_mock, current=CURRENT_OK, login_status=201):
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/status", text="1")
    aioclient_mock.post(f"{BASE}/login", status=login_status, json={"access_token": "a.b.c"})
    aioclient_mock.get(f"{BASE}/current_parameters", json=current)
    aioclient_mock.get(f"{BASE}/nominal_parameters", json={"batteryVoltageHighNominal": 12.6})
    aioclient_mock.get(f"{BASE}/device/specification", json=SPEC)
    aioclient_mock.get(
        f"{BASE}/data",
        json={"manufacturer": "MEC", "vendor": "unknown", "protocol": "Q1", "info": "V1.2"},
    )
    aioclient_mock.post(f"{BASE}/commands", text="true")


async def test_user_flow(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_app(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.20", CONF_PASSWORD: "pw"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Green Cell UPS04"
    assert result["data"][CONF_HOST] == "http://10.0.0.20:8080"
    # login body must contain exactly the password
    login = next(c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/login"))
    assert login[2] == {"password": "pw"}


async def test_user_flow_bad_password(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_app(aioclient_mock, login_status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.20", CONF_PASSWORD: "x"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def _setup(hass, options=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Green Cell UPS04",
        unique_id="http://10.0.0.20:8080",
        data={CONF_HOST: "http://10.0.0.20:8080", CONF_PASSWORD: "pw"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass, platform, key):
    ent_reg = er.async_get(hass)
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, f"{entry_id}_{key}")
    assert entity_id, key
    return hass.states.get(entity_id)


async def test_setup_and_states(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_app(aioclient_mock)
    await _setup(hass)
    assert _state(hass, "sensor", "status").state == "online"
    assert float(_state(hass, "sensor", "battery_level").state) == 100
    assert float(_state(hass, "sensor", "output_power").state) == 108
    assert _state(hass, "sensor", "temperature").state == "unknown"  # -1 = no probe
    assert _state(hass, "binary_sensor", "mains_power").state == "on"
    assert _state(hass, "binary_sensor", "fault").state == "off"
    assert _state(hass, "binary_sensor", "charging").state == "on"
    # buttons are opt-in
    ent_reg = er.async_get(hass)
    assert not [e for e in ent_reg.entities.values() if e.domain == "button"]


async def test_usb_disconnected_no_false_alarm(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_app(aioclient_mock)
    await _setup(hass)
    _mock_app(aioclient_mock, current=CURRENT_DISCONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "status").state == "disconnected"
    assert _state(hass, "binary_sensor", "fault").state == STATE_UNAVAILABLE
    assert _state(hass, "sensor", "battery_level").state == STATE_UNAVAILABLE
    assert _state(hass, "binary_sensor", "usb_connected").state == "off"


async def test_buttons_when_enabled(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_app(aioclient_mock)
    await _setup(hass, {CONF_ENABLE_CONTROLS: True})
    state = _state(hass, "button", "short_test")
    await hass.services.async_call("button", "press", {"entity_id": state.entity_id}, blocking=True)
    cmd = [c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/commands")]
    assert cmd and cmd[-1][2] == {"action": "shortTestOrder", "args": {}}


async def test_auth_failure_starts_reauth(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_app(aioclient_mock, login_status=401)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "http://10.0.0.20:8080", CONF_PASSWORD: "old"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)
