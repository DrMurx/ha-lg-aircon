"""Common base entity for the LG Aircon (IR) integration."""

from __future__ import annotations

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN


class LgAirconEntity(InfraredEmitterConsumerEntity):
    """LG Aircon base entity providing device info and the IR emitter link."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str) -> None:
        """Initialize the entity."""
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="LG",
            model="Artcool (IR)",
        )
