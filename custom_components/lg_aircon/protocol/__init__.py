"""LG 28-bit AC infrared protocol (upstream-liftable, no Home Assistant imports)."""

from .codes import LGACCode
from .command import (
    AUTO_ADJUSTMENT_LEVEL,
    MAX_TEMP,
    MIN_TEMP,
    LGACCommand,
    LGACFanSpeed,
    LGACMode,
    LGACStateCommand,
    build_state,
    checksum,
    is_valid,
)

__all__ = [
    "AUTO_ADJUSTMENT_LEVEL",
    "MAX_TEMP",
    "MIN_TEMP",
    "LGACCode",
    "LGACCommand",
    "LGACFanSpeed",
    "LGACMode",
    "LGACStateCommand",
    "build_state",
    "checksum",
    "is_valid",
]
