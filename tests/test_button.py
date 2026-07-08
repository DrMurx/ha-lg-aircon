"""Tests for the light toggle button."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_aircon.const import DOMAIN
from custom_components.lg_aircon.protocol import LGACCode

from .conftest import sent_values


async def test_light_button_sends_toggle(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send_command: AsyncMock,
) -> None:
    """Pressing the button transmits the light toggle frame."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{config_entry.entry_id}_light_toggle"
    )
    assert entity_id is not None

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert sent_values(mock_send_command) == [LGACCode.LIGHT_TOGGLE]
