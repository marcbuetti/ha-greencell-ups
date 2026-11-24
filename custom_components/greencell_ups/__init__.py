"""Green Cell UPS (GC UPS App web API) integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GCUPSApi
from .const import CONF_ENABLE_CONTROLS, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import GCUPSConfigEntry, GCUPSCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


def _platforms(entry: GCUPSConfigEntry) -> list[Platform]:
    if entry.options.get(CONF_ENABLE_CONTROLS, False):
        return [*PLATFORMS, Platform.BUTTON]
    return PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: GCUPSConfigEntry) -> bool:
    """Set up the UPS from a config entry."""
    api = GCUPSApi(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PASSWORD])
    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = GCUPSCoordinator(hass, entry, api, timedelta(seconds=interval))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _sync_device_info() -> None:
        """Model/firmware are only known once the app sees the UPS on USB."""
        data = coordinator.data
        if data is None:
            return
        registry = dr.async_get(hass)
        device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        if device is None:
            return
        changes = {
            "manufacturer": data.manufacturer,
            "model": data.model,
            "model_id": data.model_id,
            "sw_version": data.firmware,
        }
        changes = {k: v for k, v in changes.items() if v and getattr(device, k) != v}
        if changes:
            registry.async_update_device(device.id, **changes)

    entry.async_on_unload(coordinator.async_add_listener(_sync_device_info))
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GCUPSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))


async def _async_reload(hass: HomeAssistant, entry: GCUPSConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
