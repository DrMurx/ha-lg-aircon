"""Button entities for LG AC functions that are IR toggles without state."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LgAirconConfigEntry
from .entity import LgAirconEntity
from .protocol import LGACCode


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgAirconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button entities from a config entry."""
    async_add_entities([LgAirconLightButton(entry)])


class LgAirconLightButton(LgAirconEntity, ButtonEntity):
    """Toggle the display light; the IR code is a stateful toggle."""

    _attr_translation_key = "light_toggle"

    def __init__(self, entry: LgAirconConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "light_toggle")

    async def async_press(self) -> None:
        """Send the light toggle code."""
        await self._send_command(LGACCode.LIGHT_TOGGLE.to_command())
