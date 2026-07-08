"""Tests for the LG Aircon climate entity."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_aircon.const import DOMAIN
from custom_components.lg_aircon.protocol import (
    LGACCode,
    LGACFanSpeed,
    LGACMode,
    build_state,
)

from .conftest import sent_values


@pytest.fixture
def climate_id(hass: HomeAssistant, config_entry: MockConfigEntry) -> str:
    """Return the entity_id of the climate entity."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, f"{config_entry.entry_id}_climate"
    )
    assert entity_id is not None
    return entity_id


async def _call(
    hass: HomeAssistant, service: str, entity_id: str, **data: object
) -> None:
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )


async def test_initial_state(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """The entity starts in the assumed OFF state without sending anything."""
    state = hass.states.get(climate_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 21
    mock_send_command.assert_not_awaited()


async def test_power_on_frame_matches_capture(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """Changing fan while off powers on with bit 15 = 0 (capture 1)."""
    await _call(hass, SERVICE_SET_FAN_MODE, climate_id, **{ATTR_FAN_MODE: "high"})
    # Cool / 21 °C / fan High with the power-on flag == remote's Power ON press.
    assert sent_values(mock_send_command) == [0x880064A]
    assert hass.states.get(climate_id).state == HVACMode.COOL


async def test_running_adjustments_set_bit_15(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """Adjustments while running transmit the running-state flag (capture 2)."""
    await _call(hass, SERVICE_SET_FAN_MODE, climate_id, **{ATTR_FAN_MODE: "high"})
    await _call(
        hass, SERVICE_SET_TEMPERATURE, climate_id, **{ATTR_TEMPERATURE: 22}
    )
    assert sent_values(mock_send_command) == [0x880064A, 0x8808743]
    state = hass.states.get(climate_id)
    assert state.attributes[ATTR_TEMPERATURE] == 22


async def test_turn_off_uses_discrete_code_and_turn_on_resumes(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """OFF sends the one-shot power-off; ON resumes the previous state."""
    await _call(
        hass,
        SERVICE_SET_HVAC_MODE,
        climate_id,
        **{ATTR_HVAC_MODE: HVACMode.HEAT},
    )
    await _call(hass, SERVICE_TURN_OFF, climate_id)
    assert hass.states.get(climate_id).state == HVACMode.OFF

    await _call(hass, SERVICE_TURN_ON, climate_id)
    assert hass.states.get(climate_id).state == HVACMode.HEAT
    assert sent_values(mock_send_command) == [
        build_state(LGACMode.HEAT, 21, LGACFanSpeed.AUTO, power_on=True),
        LGACCode.POWER_OFF,
        build_state(LGACMode.HEAT, 21, LGACFanSpeed.AUTO, power_on=True),
    ]


async def test_auto_mode_hides_temperature(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """AUTO encodes the fixed level, not a temperature (capture 10)."""
    await _call(
        hass, SERVICE_SET_HVAC_MODE, climate_id, **{ATTR_HVAC_MODE: HVACMode.COOL}
    )
    await _call(
        hass, SERVICE_SET_HVAC_MODE, climate_id, **{ATTR_HVAC_MODE: HVACMode.AUTO}
    )
    assert sent_values(mock_send_command)[-1] == 0x880B252
    state = hass.states.get(climate_id)
    assert state.state == HVACMode.AUTO
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        & ClimateEntityFeature.TARGET_TEMPERATURE
        == 0
    )


async def test_jet_cool_preset(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """Boost sends Jet Cool and assumes Cool / 18 °C / fan High (capture 8/9)."""
    await _call(
        hass, SERVICE_SET_PRESET_MODE, climate_id, **{ATTR_PRESET_MODE: "boost"}
    )
    assert sent_values(mock_send_command) == [LGACCode.JET_COOL]
    state = hass.states.get(climate_id)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 18
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_PRESET_MODE] == "boost"

    # Any subsequent change drops the preset and sends a normal state frame.
    await _call(hass, SERVICE_SET_FAN_MODE, climate_id, **{ATTR_FAN_MODE: "medium"})
    assert sent_values(mock_send_command)[-1] == build_state(
        LGACMode.COOL, 18, LGACFanSpeed.MEDIUM
    )
    assert (
        hass.states.get(climate_id).attributes[ATTR_PRESET_MODE] == "none"
    )


async def test_swing_toggles_sent_only_on_change(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """Swing toggles are only transmitted when the assumed state changes."""
    await _call(hass, SERVICE_SET_SWING_MODE, climate_id, **{ATTR_SWING_MODE: "on"})
    await _call(hass, SERVICE_SET_SWING_MODE, climate_id, **{ATTR_SWING_MODE: "on"})
    await _call(
        hass,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        climate_id,
        **{ATTR_SWING_HORIZONTAL_MODE: "on"},
    )
    assert sent_values(mock_send_command) == [
        LGACCode.SWING_V_TOGGLE,
        LGACCode.SWING_H_TOGGLE,
    ]
    state = hass.states.get(climate_id)
    assert state.attributes[ATTR_SWING_MODE] == "on"
    assert state.attributes[ATTR_SWING_HORIZONTAL_MODE] == "on"


async def test_temperature_limits_follow_mode(
    hass: HomeAssistant, climate_id: str, mock_send_command: AsyncMock
) -> None:
    """16 °C is rejected in COOL (min 18) but accepted in HEAT (min 16)."""
    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            SERVICE_SET_TEMPERATURE,
            climate_id,
            **{ATTR_TEMPERATURE: 16, ATTR_HVAC_MODE: HVACMode.COOL},
        )
    mock_send_command.assert_not_awaited()

    await _call(
        hass, SERVICE_SET_HVAC_MODE, climate_id, **{ATTR_HVAC_MODE: HVACMode.HEAT}
    )
    await _call(
        hass, SERVICE_SET_TEMPERATURE, climate_id, **{ATTR_TEMPERATURE: 16}
    )
    assert sent_values(mock_send_command) == [
        build_state(LGACMode.HEAT, 21, LGACFanSpeed.AUTO, power_on=True),
        build_state(LGACMode.HEAT, 16, LGACFanSpeed.AUTO),
    ]
    assert hass.states.get(climate_id).attributes[ATTR_TEMPERATURE] == 16
