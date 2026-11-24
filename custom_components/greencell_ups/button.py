"""Buttons for Green Cell UPS - only loaded when "Allow control" is enabled in the options.

Deliberately limited to harmless commands. The app also accepts shutdownOrder,
shutdownAndRestoreOrder and longTestOrder (discharges the battery to "low"); none of
them is exposed: a smart home that can switch off the UPS it monitors is a risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import GCUPSError
from .coordinator import GCUPSConfigEntry
from .entity import GCUPSEntity


@dataclass(frozen=True, kw_only=True)
class GCUPSButtonDescription(ButtonEntityDescription):
    action: str


BUTTONS: tuple[GCUPSButtonDescription, ...] = (
    GCUPSButtonDescription(
        key="short_test",
        translation_key="short_test",
        entity_category=EntityCategory.CONFIG,
        action="shortTestOrder",  # ~10 s battery test
    ),
    GCUPSButtonDescription(
        key="beeper_toggle",
        translation_key="beeper_toggle",
        entity_category=EntityCategory.CONFIG,
        action="beeperToggleOrder",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GCUPSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(GCUPSButton(coordinator, desc) for desc in BUTTONS)


class GCUPSButton(GCUPSEntity, ButtonEntity):
    _entity_domain = "button"
    entity_description: GCUPSButtonDescription

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.command(self.entity_description.action)
        except GCUPSError as err:
            raise HomeAssistantError(f"UPS command failed: {err}") from err
        await self.coordinator.async_request_refresh()
