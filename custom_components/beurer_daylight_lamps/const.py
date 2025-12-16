"""Constants for the Beurer Daylight Lamps integration."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "beurer_daylight_lamps"
LOGGER = logging.getLogger(__package__)

# BLE Characteristic UUIDs
WRITE_CHARACTERISTIC_UUID: Final = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
READ_CHARACTERISTIC_UUID: Final = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"

# BLE Commands
CMD_MODE_WHITE: Final = 0x37
CMD_MODE_RGB: Final = 0x37
CMD_BRIGHTNESS: Final = 0x31
CMD_COLOR: Final = 0x32
CMD_EFFECT: Final = 0x34
CMD_OFF: Final = 0x35
CMD_STATUS: Final = 0x30

# Mode identifiers
MODE_WHITE: Final = 0x01
MODE_RGB: Final = 0x02

# Supported light effects
SUPPORTED_EFFECTS: Final[list[str]] = [
    "Off",
    "Random",
    "Rainbow",
    "Rainbow Slow",
    "Fusion",
    "Pulse",
    "Wave",
    "Chill",
    "Action",
    "Forest",
    "Summer",
]

# Connection settings
DEFAULT_SCAN_TIMEOUT: Final = 15.0
DEFAULT_CONNECT_TIMEOUT: Final = 20.0

# Device name prefixes for discovery
DEVICE_NAME_PREFIXES: Final[tuple[str, ...]] = (
    "tl100",
    "tl50",
    "tl70",
    "tl80",
    "tl90",
    "beurer",
)
