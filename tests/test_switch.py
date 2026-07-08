"""Tests for the plasma and auto-clean switches."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_aircon.const import DOMAIN
from custom_components.lg_aircon.protocol import LGACCode

from .conftest import sent_values


@pytest.mark.parametrize(
    ("key", "on_code", "off_code"),
    [
        ("plasma", LGACCode.PLASMA_ON, LGACCode.PLASMA_OFF),
        ("auto_clean", LGACCode.AUTO_CLEAN_ON, LGACCode.AUTO_CLEAN_OFF),
    ],
)
async def test_switch_sends_discrete_codes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send_command: AsyncMock,
    key: str,
    on_code: LGACCode,
    off_code: LGACCode,
) -> None:
    """Each switch transmits its discrete on/off frame and tracks state."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{config_entry.entry_id}_{key}"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    assert sent_values(mock_send_command) == [on_code, off_code]
