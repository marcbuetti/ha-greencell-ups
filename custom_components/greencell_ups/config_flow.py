"""Config flow for Green Cell UPS."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import GCUPSApi, GCUPSAuthError, GCUPSConnectionError, GCUPSError
from .const import CONF_ENABLE_CONTROLS, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL
from .coordinator import GCUPSConfigEntry
from .model import UPSData

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _validate(hass: HomeAssistant, data: Mapping[str, Any]) -> tuple[str, UPSData]:
    """Log in and read once. Returns (normalized URL, data) or raises."""
    api = GCUPSApi(async_get_clientsession(hass), data[CONF_HOST], data[CONF_PASSWORD])
    if not await api.status():
        raise GCUPSConnectionError("status endpoint did not answer '1'")
    current = await api.current_parameters()
    try:
        spec = await api.specification()
    except GCUPSError:
        spec = {}
    return api.host, UPSData(current=current, spec=spec)


class GCUPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host, data = await _validate(self.hass, user_input)
            except GCUPSAuthError:
                errors["base"] = "invalid_auth"
            except GCUPSConnectionError:
                errors["base"] = "cannot_connect"
            except GCUPSError:
                _LOGGER.exception("Unexpected response from the GC UPS App")
                errors["base"] = "unknown"
            else:
                user_input[CONF_HOST] = host
                await self.async_set_unique_id(host.lower())
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                title = f"Green Cell {data.model}" if data.model else "Green Cell UPS"
                return self.async_create_entry(title=title, data=user_input)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PASSWORD): _PASSWORD,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await _validate(self.hass, data)
            except GCUPSAuthError:
                errors["base"] = "invalid_auth"
            except GCUPSError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host/port (e.g. the PC got a new address)."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                host, _ = await _validate(self.hass, data)
            except GCUPSAuthError:
                errors["base"] = "invalid_auth"
            except GCUPSError:
                errors["base"] = "cannot_connect"
            else:
                data[CONF_HOST] = host
                other = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, host.lower()
                )
                if other is not None and other.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(entry, unique_id=host.lower(), data=data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: GCUPSConfigEntry) -> OptionsFlow:
        return GCUPSOptionsFlow()


class GCUPSOptionsFlow(OptionsFlow):
    """Polling interval and the opt-in for commands."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                    vol.Required(
                        CONF_ENABLE_CONTROLS, default=opts.get(CONF_ENABLE_CONTROLS, False)
                    ): bool,
                }
            ),
        )
