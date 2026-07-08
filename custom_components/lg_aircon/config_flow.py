"""Config flow for the LG Aircon (IR) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)
import voluptuous as vol

from .const import CONF_INFRARED_ENTITY_ID, DEFAULT_NAME, DOMAIN


def _emitter_selector(emitter_entity_ids: list[str]) -> EntitySelector:
    """Build a selector limited to the available infrared emitters."""
    return EntitySelector(
        EntitySelectorConfig(
            domain=INFRARED_DOMAIN,
            include_entities=emitter_entity_ids,
        )
    )


class LgAirconConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for an LG air conditioner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID],
                }
            )
            return self.async_create_entry(
                title=user_input[CONF_NAME], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
                    vol.Required(CONF_INFRARED_ENTITY_ID): _emitter_selector(
                        emitter_entity_ids
                    ),
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow swapping the infrared emitter of an existing entry."""
        entry = self._get_reconfigure_entry()
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID]
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INFRARED_ENTITY_ID,
                        default=entry.data[CONF_INFRARED_ENTITY_ID],
                    ): _emitter_selector(emitter_entity_ids),
                }
            ),
        )
