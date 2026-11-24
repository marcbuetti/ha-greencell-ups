"""Base entity for Green Cell UPS."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GCUPSCoordinator
from .model import UPSData


class GCUPSEntity(CoordinatorEntity[GCUPSCoordinator]):
    """One entity of the UPS behind one GC UPS App instance."""

    _attr_has_entity_name = True
    # Values that only exist while the app sees the UPS on USB. Without the link the app
    # serves placeholders (-1, failed=True, ...) - those must not look plausible.
    _needs_usb = True
    _entity_domain: str

    def __init__(self, coordinator: GCUPSCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        # Language-independent entity_id (sensor.gc_ups_battery_level, ...) so the example
        # dashboard works regardless of the HA language. A second UPS gets "_2" from HA.
        self.entity_id = f"{self._entity_domain}.gc_ups_{description.key}"
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=data.manufacturer,
            name=entry.title,
            model=data.model,
            model_id=data.model_id,
            sw_version=data.firmware,
            configuration_url=coordinator.api.host,
        )

    @property
    def ups(self) -> UPSData:
        return self.coordinator.data

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.ups.connected or not self._needs_usb
