"""Diagnostics download for Green Cell UPS (password redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import GCUPSConfigEntry

TO_REDACT = {CONF_PASSWORD, "access_token", "serial", "serialNumber"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GCUPSConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "derived": {
            "status": data.status,
            "connected": data.connected,
            "charging": data.charging,
            "output_power": data.output_power,
        },
        "current_parameters": async_redact_data(data.current, TO_REDACT),
        "nominal_parameters": data.nominal,
        "specification": async_redact_data(data.spec, TO_REDACT),
        "device_data": async_redact_data(data.info, TO_REDACT),
    }
