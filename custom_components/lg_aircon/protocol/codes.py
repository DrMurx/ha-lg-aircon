"""Fixed one-shot LG AC command codes.

All codes verified on an LG Artcool unit; see PROTOCOL.md §3. Swing and
light codes are stateful toggles at the IR level, the rest are discrete.
"""

from __future__ import annotations

from enum import IntEnum

from .command import LGACCommand


class LGACCode(IntEnum):
    """One-shot LG AC command codes (stateless frame constants)."""

    POWER_OFF = 0x88C0051
    JET_COOL = 0x8810089
    SWING_V_TOGGLE = 0x8810001
    SWING_H_TOGGLE = 0x8813004
    PLASMA_ON = 0x88C000C
    PLASMA_OFF = 0x88C0084
    AUTO_CLEAN_ON = 0x88C00B7
    AUTO_CLEAN_OFF = 0x88C00C8
    LIGHT_TOGGLE = 0x88C00A6

    def to_command(self) -> LGACCommand:
        """Return an IR command for this code."""
        return LGACCommand(self.value)
