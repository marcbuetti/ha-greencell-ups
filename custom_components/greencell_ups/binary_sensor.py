"""Binary sensors for Green Cell UPS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GCUPSConfigEntry
from .entity import GCUPSEntity
from .model import UPSData


@dataclass(frozen=True, kw_only=True)
class GCUPSBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[UPSData], bool | None]
    needs_usb: bool = True


BINARY_SENSORS: tuple[GCUPSBinaryDescription, ...] = (
    GCUPSBinaryDescription(
        key="usb_connected",
        translation_key="usb_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.connected,
        needs_usb=False,
    ),
    GCUPSBinaryDescription(
        # "Power" on = mains present. Inverse of utilityFail, so automations read naturally.
        key="mains_power",
        translation_key="mains_power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d: None if d.utility_fail is None else not d.utility_fail,
    ),
    GCUPSBinaryDescription(
        key="on_battery",
        translation_key="on_battery",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.utility_fail,
    ),
    GCUPSBinaryDescription(
        key="battery_low",
        translation_key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda d: d.battery_low,
    ),
    GCUPSBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: d.charging,
    ),
    GCUPSBinaryDescription(
        key="fault",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.failed,
    ),
    GCUPSBinaryDescription(
        key="shutdown_active",
        translation_key="shutdown_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.shutdown_active,
    ),
    GCUPSBinaryDescription(
        key="test_in_progress",
        translation_key="test_in_progress",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.test_in_progress,
    ),
    GCUPSBinaryDescription(
        key="avr_active",
        translation_key="avr_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.bypass_boost,
    ),
    GCUPSBinaryDescription(
        key="beeper",
        translation_key="beeper",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.beeper_on,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GCUPSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(GCUPSBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class GCUPSBinarySensor(GCUPSEntity, BinarySensorEntity):
    entity_description: GCUPSBinaryDescription

    def __init__(self, coordinator, description: GCUPSBinaryDescription) -> None:
        super().__init__(coordinator, description)
        self._needs_usb = description.needs_usb

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.ups)
