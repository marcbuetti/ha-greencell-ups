"""Polling coordinator for the GC UPS App."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GCUPSApi, GCUPSAuthError, GCUPSError
from .const import DOMAIN, INFO_REFRESH
from .model import UPSData

_LOGGER = logging.getLogger(__name__)

type GCUPSConfigEntry = ConfigEntry[GCUPSCoordinator]


class GCUPSCoordinator(DataUpdateCoordinator[UPSData]):
    """current_parameters every interval; nominal values, spec and vendor data hourly."""

    config_entry: GCUPSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GCUPSConfigEntry,
        api: GCUPSApi,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=scan_interval
        )
        self.api = api
        self._nominal: dict[str, Any] = {}
        self._spec: dict[str, Any] = {}
        self._info: dict[str, Any] = {}
        self._info_at: float | None = None  # monotonic() is small right after boot

    async def _refresh_info(self) -> None:
        # Each part is optional: an old app version without one route must not break polling.
        for attr, call in (
            ("_nominal", self.api.nominal_parameters),
            ("_spec", self.api.specification),
            ("_info", self.api.device_data),
        ):
            try:
                value = await call()
            except GCUPSAuthError:
                raise
            except GCUPSError as err:
                _LOGGER.debug("%s failed: %s", call.__name__, err)
                continue
            if value:
                setattr(self, attr, value)
        self._info_at = time.monotonic()

    async def _async_update_data(self) -> UPSData:
        try:
            current = await self.api.current_parameters()
            # Refresh device info hourly, and right after the USB link comes back (the app
            # answers the spec with "unknown" placeholders while the UPS is disconnected).
            age = float("inf") if self._info_at is None else time.monotonic() - self._info_at
            incomplete = current.get("connected") and self._spec.get("name") in (None, "unknown")
            if age > INFO_REFRESH or (incomplete and age > 60):
                await self._refresh_info()
        except GCUPSAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GCUPSError as err:
            raise UpdateFailed(str(err)) from err
        # The nominal fields are also merged into current_parameters by the app.
        nominal = {**self._nominal}
        for key, value in current.items():
            if key.endswith("Nominal") and key not in nominal:
                nominal[key] = value
        return UPSData(current=current, nominal=nominal, spec=self._spec, info=self._info)
