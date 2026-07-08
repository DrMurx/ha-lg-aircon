"""Climate entity that synthesizes LG AC infrared state frames.

The IR link is transmit-only: the entity is optimistic/assumed-state
throughout, and its state drifts if the physical remote is used in parallel.
The remote transmits the full device state on every press, so every change
sends a complete frame (mode + temperature + fan).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_BOOST,
    PRESET_NONE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LgAirconConfigEntry
from .entity import LgAirconEntity
from .protocol import (
    MAX_TEMP,
    MIN_TEMP,
    LGACCode,
    LGACFanSpeed,
    LGACMode,
    LGACStateCommand,
)

FAN_QUIET = "quiet"

HVAC_TO_MODE: dict[HVACMode, LGACMode] = {
    HVACMode.AUTO: LGACMode.AUTO,
    HVACMode.COOL: LGACMode.COOL,
    HVACMode.HEAT: LGACMode.HEAT,
    HVACMode.DRY: LGACMode.DRY,
    HVACMode.FAN_ONLY: LGACMode.FAN,
}

FAN_TO_SPEED: dict[str, LGACFanSpeed] = {
    FAN_QUIET: LGACFanSpeed.QUIET,
    FAN_LOW: LGACFanSpeed.LOW,
    FAN_MEDIUM: LGACFanSpeed.MEDIUM,
    FAN_HIGH: LGACFanSpeed.HIGH,
    FAN_AUTO: LGACFanSpeed.AUTO,
}

DEFAULT_TEMPERATURE = 21


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgAirconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate entity from a config entry."""
    async_add_entities([LgAirconClimate(entry)])


class LgAirconClimate(LgAirconEntity, RestoreEntity, ClimateEntity):
    """Virtual LG air conditioner controlled over infrared."""

    _attr_name = None
    _attr_translation_key = "aircon"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.OFF, *HVAC_TO_MODE]
    _attr_fan_modes = list(FAN_TO_SPEED)
    _attr_preset_modes = [PRESET_NONE, PRESET_BOOST]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_swing_horizontal_modes = [SWING_OFF, SWING_ON]

    def __init__(self, entry: LgAirconConfigEntry) -> None:
        """Initialize with the assumed power-off state."""
        super().__init__(entry, "climate")
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = FAN_AUTO
        self._attr_preset_mode = PRESET_NONE
        self._attr_swing_mode = SWING_OFF
        self._attr_swing_horizontal_mode = SWING_OFF
        self._target_temperature = DEFAULT_TEMPERATURE
        self._last_active_hvac_mode = HVACMode.COOL

    async def async_added_to_hass(self) -> None:
        """Restore the assumed state from the last known state."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is None:
            return
        try:
            hvac_mode = HVACMode(state.state)
        except ValueError:
            pass
        else:
            self._attr_hvac_mode = hvac_mode
            if hvac_mode != HVACMode.OFF:
                self._last_active_hvac_mode = hvac_mode
        if (temperature := state.attributes.get(ATTR_TEMPERATURE)) is not None:
            self._target_temperature = int(temperature)
        if (fan_mode := state.attributes.get(ATTR_FAN_MODE)) in FAN_TO_SPEED:
            self._attr_fan_mode = fan_mode
        if state.attributes.get(ATTR_PRESET_MODE) in self._attr_preset_modes:
            self._attr_preset_mode = state.attributes[ATTR_PRESET_MODE]
        if state.attributes.get(ATTR_SWING_MODE) in self._attr_swing_modes:
            self._attr_swing_mode = state.attributes[ATTR_SWING_MODE]
        if (
            state.attributes.get(ATTR_SWING_HORIZONTAL_MODE)
            in self._attr_swing_horizontal_modes
        ):
            self._attr_swing_horizontal_mode = state.attributes[
                ATTR_SWING_HORIZONTAL_MODE
            ]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features; no target temperature in AUTO mode."""
        features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.SWING_HORIZONTAL_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self._attr_hvac_mode != HVACMode.AUTO:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature; AUTO mode has none (level-based)."""
        if self._attr_hvac_mode == HVACMode.AUTO:
            return None
        return float(self._target_temperature)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature for the active mode."""
        mode = HVAC_TO_MODE[self._active_hvac_mode()]
        return float(MIN_TEMP.get(mode, MIN_TEMP[LGACMode.COOL]))

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return float(MAX_TEMP)

    def _active_hvac_mode(self) -> HVACMode:
        """Return the current mode, or the mode to resume when off."""
        if self._attr_hvac_mode == HVACMode.OFF:
            return self._last_active_hvac_mode
        return self._attr_hvac_mode

    async def _async_send_state(
        self,
        hvac_mode: HVACMode | None = None,
        temperature: int | None = None,
        fan_mode: str | None = None,
    ) -> None:
        """Send a full state frame for the requested (partial) target state."""
        target_mode = hvac_mode or self._active_hvac_mode()
        target_fan = fan_mode or self._attr_fan_mode or FAN_AUTO
        command = LGACStateCommand(
            mode=HVAC_TO_MODE[target_mode],
            temperature=(
                int(temperature)
                if temperature is not None
                else self._target_temperature
            ),
            fan=FAN_TO_SPEED[target_fan],
            power_on=self._attr_hvac_mode == HVACMode.OFF,
        )
        await self._send_command(command)
        self._attr_hvac_mode = target_mode
        self._last_active_hvac_mode = target_mode
        if command.mode is not LGACMode.AUTO:
            self._target_temperature = command.temperature  # clamped by the encoder
        self._attr_fan_mode = target_fan
        self._attr_preset_mode = PRESET_NONE
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode; OFF uses the discrete power-off code."""
        if hvac_mode == HVACMode.OFF:
            await self._send_command(LGACCode.POWER_OFF.to_command())
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_preset_mode = PRESET_NONE
            self.async_write_ha_state()
            return
        await self._async_send_state(hvac_mode=hvac_mode)

    async def async_turn_on(self) -> None:
        """Turn on by resuming the last active mode."""
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._async_send_state()

    async def async_turn_off(self) -> None:
        """Turn the unit off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature (optionally with a new HVAC mode)."""
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.OFF)
            return
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._async_send_state(
            hvac_mode=hvac_mode,
            temperature=None if temperature is None else int(temperature),
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan speed."""
        await self._async_send_state(fan_mode=fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the Jet Cool preset, or return to a normal state frame."""
        if preset_mode == PRESET_BOOST:
            await self._send_command(LGACCode.JET_COOL.to_command())
            # The unit self-sets Cool / 18 °C / fan High after Jet Cool.
            self._attr_preset_mode = PRESET_BOOST
            self._attr_hvac_mode = HVACMode.COOL
            self._last_active_hvac_mode = HVACMode.COOL
            self._target_temperature = MIN_TEMP[LGACMode.COOL]
            self._attr_fan_mode = FAN_HIGH
            self.async_write_ha_state()
        elif self._attr_preset_mode != PRESET_NONE:
            await self._async_send_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set vertical swing; the IR code is a toggle, tracked optimistically."""
        if swing_mode != self._attr_swing_mode:
            await self._send_command(LGACCode.SWING_V_TOGGLE.to_command())
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set horizontal swing; the IR code is a toggle, tracked optimistically."""
        if swing_horizontal_mode != self._attr_swing_horizontal_mode:
            await self._send_command(LGACCode.SWING_H_TOGGLE.to_command())
            self._attr_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()
