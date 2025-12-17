"""Constants for the Beurer Daylight Lamps integration."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "beurer_daylight_lamps"
VERSION: Final = "1.9.0"
LOGGER = logging.getLogger(__package__)

# BLE Characteristic UUIDs
WRITE_CHARACTERISTIC_UUID: Final = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
READ_CHARACTERISTIC_UUID: Final = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"

# BLE Protocol Commands
# These are the first byte of the command payload
CMD_STATUS: Final = 0x30      # Request current status
CMD_BRIGHTNESS: Final = 0x31  # Set brightness (0-100%)
CMD_COLOR: Final = 0x32       # Set RGB color
CMD_EFFECT: Final = 0x34      # Set light effect
CMD_OFF: Final = 0x35         # Turn off
CMD_MODE: Final = 0x37        # Set mode (white/rgb)

# Mode identifiers (second byte after CMD_MODE, CMD_BRIGHTNESS, CMD_OFF, CMD_STATUS)
MODE_WHITE: Final = 0x01
MODE_RGB: Final = 0x02

# Timing constants for BLE communication
# The device needs delays between commands to process them correctly
COMMAND_DELAY: Final = 0.3      # Standard delay after most commands
MODE_CHANGE_DELAY: Final = 0.5  # Longer delay after mode changes
EFFECT_DELAY: Final = 0.5       # Delay after effect changes
STATUS_DELAY: Final = 0.2       # Delay after status request
TURN_OFF_DELAY: Final = 0.15    # Short delay after turn off sequence

# Rate limiting for commands to prevent overwhelming the device
MIN_COMMAND_INTERVAL: Final = 0.1  # Minimum time between commands (100ms)

# Supported light effects (index corresponds to protocol value)
SUPPORTED_EFFECTS: Final[list[str]] = [
    "Off",           # 0
    "Random",        # 1
    "Rainbow",       # 2
    "Rainbow Slow",  # 3
    "Fusion",        # 4
    "Pulse",         # 5
    "Wave",          # 6
    "Chill",         # 7
    "Action",        # 8
    "Forest",        # 9
    "Summer",        # 10
]

# Device name prefixes for discovery (lowercase for case-insensitive matching)
# Only specific TL model prefixes to avoid conflicts with other Beurer devices
DEVICE_NAME_PREFIXES: Final[tuple[str, ...]] = (
    "tl100",
    "tl50",
    "tl70",
    "tl80",
    "tl90",
)

# Model detection map based on device name prefixes
MODEL_MAP: Final[dict[str, str]] = {
    "TL100": "TL100 Daylight Therapy Lamp",
    "TL50": "TL50 Daylight Therapy Lamp",
    "TL70": "TL70 Daylight Therapy Lamp",
    "TL80": "TL80 Daylight Therapy Lamp",
    "TL90": "TL90 Daylight Therapy Lamp",
}


def detect_model(name: str | None) -> str:
    """Detect model from device name.

    Args:
        name: Device name to check

    Returns:
        Model string based on device name prefix, or generic fallback.
    """
    if not name:
        return "Daylight Therapy Lamp"
    name_upper = name.upper()
    for prefix, model in MODEL_MAP.items():
        if name_upper.startswith(prefix):
            return model
    return "Daylight Therapy Lamp"
