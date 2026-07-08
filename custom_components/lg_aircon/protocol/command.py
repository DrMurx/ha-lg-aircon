"""Encoder for the LG 28-bit AC infrared protocol ("LG2").

Frame layout and physical-layer timings were decoded from an LG remote,
model 6711Z90031C, and verified against 26 captured presses; see PROTOCOL.md
in the repository root.

This module is deliberately free of Home Assistant imports and mirrors the
structure of infrared_protocols.commands.panasonic_ac so it can be lifted
into the infrared-protocols library unchanged.
"""

from __future__ import annotations

from enum import IntEnum

from infrared_protocols.commands import Command

LG_AC_BITS = 28
LG_AC_SIGN = 0x88

# Physical layer (microseconds), pulse-distance coding at 38 kHz.
_HEADER_MARK = 8834
_HEADER_SPACE = 4466
_BIT_MARK = 558
_ZERO_SPACE = 558
_ONE_SPACE = 1741
_END_GAP = 109460

_MODULATION = 38000

# In AUTO (AI) mode the temperature nibble is not a temperature but an
# adjustment level; 2 is the observed center of the presumed -2..+2 scale.
AUTO_ADJUSTMENT_LEVEL = 2


class LGACMode(IntEnum):
    """Operating mode nibble (frame bits 14-12)."""

    COOL = 0
    DRY = 1
    FAN = 2  # in the reference implementation; not observed on remote 6711Z90031C
    AUTO = 3
    HEAT = 4


class LGACFanSpeed(IntEnum):
    """Fan speed nibble (frame bits 7-4)."""

    QUIET = 0
    LOW = 1  # in the reference implementation; not observed on remote 6711Z90031C
    MEDIUM = 2
    HIGH = 4
    AUTO = 5


# The unit clamps the target temperature depending on mode; the frame nibble
# itself can encode 15-30 °C.
MIN_TEMP: dict[LGACMode, int] = {
    LGACMode.COOL: 18,
    LGACMode.DRY: 18,
    LGACMode.FAN: 18,
    LGACMode.HEAT: 16,
}
MAX_TEMP = 30


def checksum(value: int) -> int:
    """Return the checksum nibble for a frame: sum of nibbles 1-4, mod 16."""
    return (
        ((value >> 4) & 0xF)
        + ((value >> 8) & 0xF)
        + ((value >> 12) & 0xF)
        + ((value >> 16) & 0xF)
    ) & 0xF


def is_valid(value: int) -> bool:
    """Check the sign byte and checksum of a 28-bit frame."""
    return (value >> 20) == LG_AC_SIGN and (value & 0xF) == checksum(value)


def build_state(mode: int, temp_c: int, fan: int, power_on: bool = False) -> int:
    """Build a 28-bit state frame from mode, temperature (°C) and fan nibbles.

    The remote transmits bit 15 = 0 on the power-on press (unit was off) and
    bit 15 = 1 for every adjustment while running; ``power_on`` selects that
    behavior. Any valid state frame switches the unit on - switching off uses
    the discrete one-shot code instead.
    """
    v = LG_AC_SIGN << 20
    if not power_on:
        v |= 1 << 15
    v |= (mode & 0x7) << 12
    v |= ((temp_c - 15) & 0xF) << 8
    v |= (fan & 0xF) << 4
    return v | checksum(v)


class LGACCommand(Command):
    """A raw 28-bit LG AC frame."""

    def __init__(
        self,
        value: int,
        *,
        modulation: int = _MODULATION,
        repeat_count: int = 0,
    ) -> None:
        """Initialize the command from a 28-bit frame value."""
        super().__init__(modulation=modulation, repeat_count=repeat_count)
        self.value = value & 0xFFFFFFF

    def get_raw_timings(self) -> list[int]:
        """Return the frame as mark (positive) / space (negative) durations."""
        timings = [_HEADER_MARK, -_HEADER_SPACE]
        for bit in range(LG_AC_BITS - 1, -1, -1):
            timings.append(_BIT_MARK)
            timings.append(
                -_ONE_SPACE if (self.value >> bit) & 1 else -_ZERO_SPACE
            )
        timings.append(_BIT_MARK)
        timings.append(-_END_GAP)
        return timings

    def __eq__(self, other: object) -> bool:
        """Compare commands by frame value."""
        if not isinstance(other, LGACCommand):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        """Hash by frame value."""
        return hash(self.value)

    def __repr__(self) -> str:
        """Represent the command by its frame value."""
        return f"{type(self).__name__}(0x{self.value:07X})"


class LGACStateCommand(LGACCommand):
    """A full device state frame (mode + temperature + fan).

    In AUTO mode the temperature is ignored and the fixed adjustment level is
    encoded instead. For all other modes the temperature is clamped to the
    unit's supported range.
    """

    def __init__(
        self,
        *,
        mode: LGACMode,
        temperature: int,
        fan: LGACFanSpeed = LGACFanSpeed.AUTO,
        power_on: bool = False,
        modulation: int = _MODULATION,
    ) -> None:
        """Initialize the state command."""
        self.mode = mode
        self.fan = fan
        self.power_on = power_on
        if mode is LGACMode.AUTO:
            temp_c = AUTO_ADJUSTMENT_LEVEL + 15  # encodes the raw level nibble
        else:
            temperature = max(MIN_TEMP[mode], min(MAX_TEMP, int(temperature)))
            temp_c = temperature
        self.temperature = temperature
        super().__init__(
            build_state(mode, temp_c, fan, power_on), modulation=modulation
        )
