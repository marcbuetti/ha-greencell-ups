"""Sensors for Green Cell UPS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GCUPSConfigEntry
from .entity import GCUPSEntity
from .model import STATUSES, UPSData, measurement


@dataclass(frozen=True, kw_only=True)
class GCUPSSensorDescription(SensorEntityDescription):
    value_fn: Callable[[UPSData], Any]
    needs_usb: bool = True


def _nominal(*keys: str) -> Callable[[UPSData], float | None]:
    return lambda d: measurement(d.nominal, *keys)


def _spec(key: str) -> Callable[[UPSData], float | None]:
    return lambda d: measurement(d.spec, key)


_VOLT = {
    "device_class": SensorDeviceClass.VOLTAGE,
    "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
}

SENSORS: tuple[GCUPSSensorDescription, ...] = (
    GCUPSSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUSES,
        value_fn=lambda d: d.status,
        needs_usb=False,
    ),
    GCUPSSensorDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.battery_level,
    ),
    GCUPSSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.battery_voltage,
        **_VOLT,
    ),
    GCUPSSensorDescription(
        key="input_voltage",
        translation_key="input_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.input_voltage,
        **_VOLT,
    ),
    GCUPSSensorDescription(
        key="input_voltage_fault",
        translation_key="input_voltage_fault",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.input_voltage_fault,
        **_VOLT,
    ),
    GCUPSSensorDescription(
        key="output_voltage",
        translation_key="output_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.output_voltage,
        **_VOLT,
    ),
    GCUPSSensorDescription(
        key="input_frequency",
        translation_key="input_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.input_frequency,
    ),
    GCUPSSensorDescription(
        key="load",
        translation_key="load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.load,
    ),
    GCUPSSensorDescription(
        key="output_power",
        translation_key="output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.output_power,
    ),
    GCUPSSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temperature,
    ),
    # --- rated values (diagnostic) ------------------------------------------------------
    GCUPSSensorDescription(
        key="rated_power",
        translation_key="rated_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.rated_power,
        needs_usb=False,
    ),
    GCUPSSensorDescription(
        key="rated_capacity",
        translation_key="rated_capacity",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_spec("capacity"),
        needs_usb=False,
    ),
    GCUPSSensorDescription(
        key="battery_voltage_nominal",
        translation_key="battery_voltage_nominal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_nominal("batteryVoltageNominal", "battery_voltage_nominal"),
        needs_usb=False,
        **_VOLT,
    ),
    GCUPSSensorDescription(
        key="input_voltage_nominal",
        translation_key="input_voltage_nominal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_nominal("inputVoltageNominal", "input_voltage_nominal"),
        needs_usb=False,
        **_VOLT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GCUPSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(GCUPSSensor(coordinator, desc) for desc in SENSORS)


class GCUPSSensor(GCUPSEntity, SensorEntity):
    entity_description: GCUPSSensorDescription

    def __init__(self, coordinator, description: GCUPSSensorDescription) -> None:
        super().__init__(coordinator, description)
        self._needs_usb = description.needs_usb

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.ups)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "status":
            return None
        d = self.ups
        return {
            "usb_connected": d.connected,
            "on_battery": d.utility_fail,
            "charging": d.charging,
        }
