"""Switch entities for LG AC functions with discrete on/off IR codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LgAirconConfigEntry
from .entity import LgAirconEntity
from .protocol import LGACCode


@dataclass(frozen=True, kw_only=True)
class LgAirconSwitchDescription(SwitchEntityDescription):
    """Describes an LG AC switch backed by discrete IR codes."""

    on_code: LGACCode
    off_code: LGACCode


SWITCHES: tuple[LgAirconSwitchDescription, ...] = (
    LgAirconSwitchDescription(
        key="plasma",
        translation_key="plasma",
        on_code=LGACCode.PLASMA_ON,
        off_code=LGACCode.PLASMA_OFF,
    ),
    LgAirconSwitchDescription(
        key="auto_clean",
        translation_key="auto_clean",
        on_code=LGACCode.AUTO_CLEAN_ON,
        off_code=LGACCode.AUTO_CLEAN_OFF,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgAirconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch entities from a config entry."""
    async_add_entities(
        LgAirconSwitch(entry, description) for description in SWITCHES
    )


class LgAirconSwitch(LgAirconEntity, RestoreEntity, SwitchEntity):
    """A switch sending discrete IR on/off codes (state still assumed)."""

    entity_description: LgAirconSwitchDescription

    def __init__(
        self, entry: LgAirconConfigEntry, description: LgAirconSwitchDescription
    ) -> None:
        """Initialize the switch."""
        super().__init__(entry, description.key)
        self.entity_description = description
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Restore the assumed state from the last known state."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_is_on = state.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the discrete ON code."""
        await self._send_command(self.entity_description.on_code.to_command())
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the discrete OFF code."""
        await self._send_command(self.entity_description.off_code.to_command())
        self._attr_is_on = False
        self.async_write_ha_state()
