"""Tests for the LG AC protocol encoder against the PROTOCOL.md §9 captures."""

from __future__ import annotations

import pytest

from custom_components.lg_aircon.protocol import (
    AUTO_ADJUSTMENT_LEVEL,
    LGACCode,
    LGACCommand,
    LGACFanSpeed,
    LGACMode,
    LGACStateCommand,
    build_state,
    checksum,
    is_valid,
)

# Every state-frame capture from PROTOCOL.md §9:
# (value, mode, temp °C, fan, power_on)
CAPTURED_STATE_FRAMES = [
    (0x880064A, LGACMode.COOL, 21, LGACFanSpeed.HIGH, True),  # Power ON press
    (0x8808743, LGACMode.COOL, 22, LGACFanSpeed.HIGH, False),
    (0x8808642, LGACMode.COOL, 21, LGACFanSpeed.HIGH, False),
    (0x8808653, LGACMode.COOL, 21, LGACFanSpeed.AUTO, False),
    (0x880860E, LGACMode.COOL, 21, LGACFanSpeed.QUIET, False),
    (0x8808620, LGACMode.COOL, 21, LGACFanSpeed.MEDIUM, False),
    (0x880834F, LGACMode.COOL, 18, LGACFanSpeed.HIGH, False),
    (0x8809801, LGACMode.DRY, 23, LGACFanSpeed.QUIET, False),
    (0x880CF4F, LGACMode.HEAT, 30, LGACFanSpeed.HIGH, False),
]


@pytest.mark.parametrize(
    ("value", "mode", "temp", "fan", "power_on"), CAPTURED_STATE_FRAMES
)
def test_build_state_matches_captures(value, mode, temp, fan, power_on) -> None:
    """build_state must reproduce every captured state frame bit-for-bit."""
    assert build_state(mode, temp, fan, power_on=power_on) == value


@pytest.mark.parametrize(
    ("value", "mode", "temp", "fan", "power_on"), CAPTURED_STATE_FRAMES
)
def test_state_command_matches_captures(value, mode, temp, fan, power_on) -> None:
    """LGACStateCommand must reproduce every captured state frame."""
    command = LGACStateCommand(
        mode=mode, temperature=temp, fan=fan, power_on=power_on
    )
    assert command.value == value


def test_auto_mode_encodes_adjustment_level() -> None:
    """AUTO mode ignores the temperature and encodes the fixed level (capture 10)."""
    assert AUTO_ADJUSTMENT_LEVEL == 2
    for temperature in (16, 21, 30):
        command = LGACStateCommand(
            mode=LGACMode.AUTO, temperature=temperature, fan=LGACFanSpeed.AUTO
        )
        assert command.value == 0x880B252


@pytest.mark.parametrize("code", list(LGACCode))
def test_one_shot_codes_have_valid_checksums(code: LGACCode) -> None:
    """All one-shot codes carry the 0x88 sign and a valid checksum."""
    assert is_valid(code.value)
    assert code.to_command().value == code.value


@pytest.mark.parametrize(("value", "_m", "_t", "_f", "_p"), CAPTURED_STATE_FRAMES)
def test_captured_frames_have_valid_checksums(value, _m, _t, _f, _p) -> None:
    """Sanity: the capture table itself checksums correctly."""
    assert is_valid(value)


@pytest.mark.parametrize(
    ("mode", "requested", "clamped"),
    [
        (LGACMode.COOL, 15, 18),
        (LGACMode.COOL, 31, 30),
        (LGACMode.HEAT, 15, 16),
        (LGACMode.HEAT, 31, 30),
    ],
)
def test_temperature_clamping(mode, requested, clamped) -> None:
    """Temperatures are clamped to the unit's per-mode limits."""
    command = LGACStateCommand(
        mode=mode, temperature=requested, fan=LGACFanSpeed.HIGH
    )
    assert command.temperature == clamped
    assert command.value == build_state(mode, clamped, LGACFanSpeed.HIGH)


def test_power_on_clears_bit_15() -> None:
    """Bit 15 is 0 only on the off->on transition (PROTOCOL.md §2.1)."""
    on = build_state(LGACMode.COOL, 21, LGACFanSpeed.HIGH, power_on=True)
    running = build_state(LGACMode.COOL, 21, LGACFanSpeed.HIGH, power_on=False)
    assert not on & (1 << 15)
    assert running & (1 << 15)
    assert on | (1 << 15) | checksum(on | (1 << 15)) != on  # frames differ


def _decode_timings(timings: list[int]) -> int:
    """Rebuild the 28-bit value from raw timings (inverse of the encoder)."""
    # Strip header (2), trailing mark + end gap (2); pairs of mark/space remain.
    bit_pairs = timings[2:-2]
    assert len(bit_pairs) == 56
    value = 0
    for space in bit_pairs[1::2]:
        value = (value << 1) | (1 if -space > 1000 else 0)
    return value


@pytest.mark.parametrize(
    "value", [v for v, *_ in CAPTURED_STATE_FRAMES] + [c.value for c in LGACCode]
)
def test_raw_timings_round_trip(value: int) -> None:
    """get_raw_timings encodes the frame so that decoding restores the value."""
    command = LGACCommand(value)
    timings = command.get_raw_timings()
    assert len(timings) == 60
    assert timings[0] == 8834  # header mark
    assert timings[1] == -4466  # header space
    assert timings[-2] == 558  # trailing mark
    assert timings[-1] == -109460  # end gap
    assert all(t != 0 for t in timings)
    assert all((t > 0) == (i % 2 == 0) for i, t in enumerate(timings))
    assert _decode_timings(timings) == value


def test_command_defaults() -> None:
    """Commands transmit once at the standard LG carrier frequency."""
    command = LGACCode.POWER_OFF.to_command()
    assert command.modulation == 38000
    assert command.repeat_count == 0
