"""Constants for the Beurer Daylight Lamps integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "beurer_daylight_lamps"
VERSION: Final = "1.38.0"

# Color temperature at or above which light.turn_on and presets use the native
# white LEDs (TL100 daylight is 5300 K) instead of emulating it with RGB.
WHITE_MODE_THRESHOLD_KELVIN: Final = 5000
LOGGER = logging.getLogger(__package__)

# BLE Characteristic UUIDs
WRITE_CHARACTERISTIC_UUID: Final = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
READ_CHARACTERISTIC_UUID: Final = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"

# BLE Protocol Commands (from APK reverse engineering)
# These are the first byte of the command payload
CMD_DEVICE_PERMISSION: Final = 0x00  # Request device control permission
CMD_TIME_SYNC: Final = 0x01  # Sync time to device
CMD_SETTINGS_WRITE: Final = 0x02  # Write device settings
CMD_SETTINGS_READ: Final = 0x12  # Read device settings

CMD_STATUS: Final = 0x30  # Request current status
CMD_BRIGHTNESS: Final = 0x31  # Set brightness (0-100%)
CMD_COLOR: Final = 0x32  # Set RGB color
CMD_EFFECT: Final = 0x34  # Set light effect
CMD_OFF: Final = 0x35  # Turn off
CMD_MODE: Final = 0x37  # Set mode (white/rgb)
CMD_TIMER_VALUE: Final = 0x33  # Set timer duration: 0x33 MODE MINUTES (slider)
CMD_TIMER_CANCEL: Final = 0x36  # Cancel timer: 0x36 MODE
CMD_TIMER_TOGGLE: Final = 0x38  # Toggle timer on/off: 0x38 MODE

# Response command bytes (data[7] in notification packets)
# Used to identify response type before version-based routing
RESP_DEVICE_PERMISSION: Final = 0xF0  # Device permission response (value must be 2)
RESP_STATUS: Final = 0xD0  # Status query response (normal)
RESP_SETTINGS_FROM_DEVICE: Final = 0xE2  # Settings read response
RESP_SETTINGS_SYNC: Final = 0xF2  # Settings write confirmation
RESP_LIGHT_TIMER_END: Final = 0xEB  # Light/white timer expired
RESP_MOONLIGHT_TIMER_END: Final = 0xEC  # Moonlight/RGB timer expired
RESP_RADIO_TIMER_END: Final = 0xED  # Radio timer expired (WL90 only)
RESP_MUSIC_TIMER_END: Final = 0xEE  # Music timer expired (WL90 only)

# WL90-specific commands (from APK reverse engineering)
# Alarm commands
CMD_ALARM_SYNC: Final = 0x03  # Sync alarm: 0x03 SLOT ENABLED MIN HOUR DAYS TONE VOL SNOOZE SUN_EN SUN_TIME SUN_BRIGHT

# Radio commands
CMD_RADIO_SYNC_INFO: Final = 0x04  # Query radio presets
CMD_RADIO_SYNC_STATUS: Final = 0x07  # Query radio status
CMD_RADIO_POWER: Final = 0x08  # Radio on/off: 0x08 STATE
CMD_RADIO_PRESET: Final = 0x09  # Select radio preset: 0x09 CHANNEL
CMD_RADIO_TUNE: Final = (
    0x0A  # Tune/seek: 0x0A TYPE DIRECTION (type: 0=fine, 1=auto-seek)
)
CMD_RADIO_VOLUME: Final = 0x0B  # Set volume: 0x0B VOLUME (0-10)
CMD_RADIO_TIMER_TOGGLE: Final = 0x0C  # Radio sleep timer on/off
CMD_RADIO_TIMER_VALUE: Final = 0x0D  # Radio sleep timer minutes
CMD_RADIO_SAVE_FREQ: Final = 0x0E  # Save frequency to preset

# Music/BT Speaker commands
CMD_MUSIC_QUERY: Final = 0x0F  # Query BT speaker status
CMD_MUSIC_TOGGLE: Final = 0x10  # BT speaker on/off
CMD_MUSIC_VOLUME: Final = 0x14  # Music volume: 0x14 VOLUME (0-10)
CMD_MUSIC_TIMER_TOGGLE: Final = 0x15  # Music sleep timer on/off
CMD_MUSIC_TIMER_VALUE: Final = 0x16  # Music sleep timer minutes
CMD_MUSIC_INFO: Final = 0x17  # Get music info
CMD_MUSIC_CLOSE: Final = 0x24  # Close BT speaker

# WL90 response command bytes
RESP_ALARM: Final = 0xF3  # Alarm data response
RESP_RADIO_INFO: Final = 0xF4  # Radio preset info
RESP_RADIO_STATUS: Final = 0xF7  # Radio status response
RESP_RADIO_POWER: Final = 0xF8  # Radio power confirmation
RESP_RADIO_PRESET: Final = 0xF9  # Radio preset confirmation
RESP_RADIO_TUNE: Final = 0xFA  # Radio tune confirmation
RESP_RADIO_SAVE: Final = 0xFE  # Radio save confirmation
RESP_MUSIC_STATUS: Final = 0xFF  # Music status response
RESP_MUSIC_TOGGLE: Final = 0xE0  # Music toggle confirmation
RESP_MUSIC_TIMER: Final = 0xE5  # Music timer confirmation
RESP_MUSIC_INFO: Final = 0xE7  # Music info response

# WL75-specific protocol commands (Protocol 2 - from APK reverse engineering)
CMD_WL75_PERMISSION: Final = 0x00  # Request permission [0x00, 0x75]
CMD_WL75_SETTINGS_READ: Final = 0x01  # Read device settings [0x01]
CMD_WL75_SETTINGS_WRITE: Final = (
    0x02  # Write device settings [0x02, display, date, time, !feedback]
)
CMD_WL75_TIME_SYNC: Final = (
    0x03  # Sync time [0x03, sec, min, hour, day, month, year-2000]
)
CMD_WL75_ALARM_READ: Final = 0x04  # Read alarm [0x04, slot] (slot 1 or 2)
CMD_WL75_ALARM_WRITE: Final = 0x05  # Write alarm [0x05, slot, min, hour, (en<<7)|days, tone, vol, snooze, wake, sun, light]
CMD_WL75_RADIO_STATUS: Final = 0x06  # Read radio status [0x06]
CMD_WL75_RADIO_PRESETS_1: Final = 0x07  # Read radio presets 1-5 [0x07]
CMD_WL75_RADIO_PRESETS_2: Final = 0x08  # Read radio presets 6-10 [0x08]
CMD_WL75_RADIO_POWER: Final = 0x09  # Radio on/off [0x09, 1/0]
CMD_WL75_RADIO_CHANNEL: Final = 0x0A  # Set preset channel [0x0A, channel] (1-10)
CMD_WL75_RADIO_SEEK: Final = 0x0B  # Search channel [0x0B, dir] (0=prev, 1=next)
CMD_WL75_RADIO_FINE_TUNE: Final = 0x0C  # Fine tuning [0x0C, dir] (0=prev, 1=next)
CMD_WL75_RADIO_VOLUME: Final = 0x0D  # Radio volume [0x0D, vol] (1-10)
CMD_WL75_RADIO_TIMER_TOGGLE: Final = 0x0E  # Radio sleep timer enable [0x0E, 1/0]
CMD_WL75_RADIO_TIMER_VALUE: Final = 0x0F  # Radio sleep timer minutes [0x0F, minutes]
CMD_WL75_RADIO_SAVE_FREQ: Final = 0x10  # Save frequency [0x10]
CMD_WL75_LIGHT_STATUS: Final = 0x11  # Request white light status [0x11]
CMD_WL75_LIGHT_SWITCH: Final = 0x12  # White light switch [0x12, 1/0]
CMD_WL75_LIGHT_BRIGHTNESS: Final = 0x13  # White light brightness [0x13, brightness]
CMD_WL75_LIGHT_TIMER_SWITCH: Final = 0x14  # White light timer switch [0x14, 1/0]
CMD_WL75_LIGHT_TIMER_VALUE: Final = 0x15  # White light timer minutes [0x15, minutes]
CMD_WL75_MOODLIGHT_STATUS: Final = 0x16  # Request moodlight status [0x16]
CMD_WL75_MOODLIGHT_SWITCH: Final = 0x17  # Moodlight switch [0x17, 1/0]
CMD_WL75_MOODLIGHT_BRIGHTNESS: Final = 0x18  # Moodlight brightness [0x18, brightness]
CMD_WL75_MOODLIGHT_TIMER_SWITCH: Final = 0x19  # Moodlight timer switch [0x19, 1/0]
CMD_WL75_MOODLIGHT_TIMER_VALUE: Final = 0x1A  # Moodlight timer minutes [0x1A, minutes]
CMD_WL75_MOODLIGHT_COLOR: Final = 0x1B  # Moodlight color [0x1B, r, g, b]
CMD_WL75_MOODLIGHT_SCENE: Final = 0x1C  # Moodlight scene [0x1C, scene]
CMD_WL75_SLEEP_STATUS: Final = 0x1D  # Sleep status [0x1D]
CMD_WL75_SLEEP_ENABLE: Final = 0x1E  # Sleep enable [0x1E, 1/0]
CMD_WL75_SLEEP_INFO: Final = 0x1F  # Set sleep info [0x1F, part, ...]

# WL75 response command bytes (first byte of resolved payload)
RESP_WL75_SAVE_RADIO_FREQ: Final = 0xE0  # Save radio frequency confirmation (-32)
RESP_WL75_LIGHT_STATUS: Final = 0xE1  # White light status (-31)
RESP_WL75_LIGHT_SWITCH: Final = 0xE2  # White light switch confirmation (-30)
RESP_WL75_LIGHT_BRIGHTNESS: Final = 0xE3  # White light brightness confirmation (-29)
RESP_WL75_MOODLIGHT_STATUS: Final = 0xE6  # Moodlight status (-26)
RESP_WL75_MOODLIGHT_SWITCH: Final = 0xE7  # Moodlight switch confirmation (-25)
RESP_WL75_MOODLIGHT_BRIGHTNESS: Final = 0xE8  # Moodlight brightness confirmation (-24)
RESP_WL75_MOODLIGHT_TIMER: Final = 0xE9  # Moodlight timer confirmation (-23)
RESP_WL75_MOODLIGHT_TIME: Final = 0xEA  # Moodlight time length confirmation (-22)
RESP_WL75_MOODLIGHT_COLOR: Final = 0xEB  # Moodlight color confirmation (-21)
RESP_WL75_MOODLIGHT_SCENE: Final = 0xEC  # Moodlight scene confirmation (-20)
RESP_WL75_SLEEP_STATUS: Final = 0xED  # Sleep status (-19)
RESP_WL75_SLEEP_ENABLE: Final = 0xEE  # Sleep enable confirmation (-18)
RESP_WL75_PERMISSION: Final = 0xF0  # Permission response (-16, value 0x75)
RESP_WL75_SETTINGS: Final = 0xF1  # Settings response (-15)
RESP_WL75_UPDATE_SETTINGS: Final = 0xF2  # Settings update confirmation (-14)
RESP_WL75_UPDATE_TIME: Final = 0xF3  # Time update confirmation (-13)
RESP_WL75_ALARM: Final = 0xF4  # Alarm response (-12)
RESP_WL75_UPDATE_ALARM: Final = 0xF5  # Alarm update confirmation (-11)
RESP_WL75_RADIO_STATUS: Final = 0xF6  # Radio status response (-10)
RESP_WL75_RADIO_PRESETS_1: Final = 0xF7  # Radio presets 1-5 (-9)
RESP_WL75_RADIO_PRESETS_2: Final = 0xF8  # Radio presets 6-10 (-8)
RESP_WL75_RADIO_POWER: Final = 0xF9  # Radio power confirmation (-7)
RESP_WL75_RADIO_CHANNEL: Final = 0xFA  # Radio channel confirmation (-6)
RESP_WL75_RADIO_SEARCH: Final = 0xFB  # Radio search response (-5)
RESP_WL75_RADIO_FINE_TUNE: Final = 0xFC  # Radio fine-tuning response (-4)
RESP_WL75_RADIO_VOLUME: Final = 0xFD  # Radio volume confirmation (-3)
RESP_WL75_RADIO_SLEEP_TIMER_ENABLE: Final = (
    0xFE  # Radio sleep timer enable confirm (-2)
)
RESP_WL75_RADIO_SLEEP_TIMER_VALUE: Final = 0xFF  # Radio sleep timer value confirm (-1)
RESP_WL75_TIMER_END: Final = 0xB0  # Timer end notification (-80)

# WL90 alarm slot mapping (position -> direction byte with high bit set)
ALARM_SLOT_MAP: Final[dict[int, int]] = {
    0: 0x81,  # Alarm 1 (index 1 | 0x80)
    1: 0x87,  # Alarm 2 (index 7 | 0x80)
    2: 0x83,  # Alarm 3 (index 3 | 0x80)
}

# Mode identifiers (second byte after CMD_MODE, CMD_BRIGHTNESS, CMD_OFF, CMD_STATUS)
MODE_WHITE: Final = 0x01
MODE_RGB: Final = 0x02

# Timing constants for BLE communication
# The device needs delays between commands to process them correctly
COMMAND_DELAY: Final = 0.3  # Standard delay after most commands
MODE_CHANGE_DELAY: Final = 0.5  # Longer delay after mode changes
# Extra settle window after a mode switch before any further functional
# command (color/brightness/effect). Firmware crashed when chained commands
# arrived too soon after CMD_MODE in white<->RGB transitions.
MODE_SWITCH_SETTLE_DELAY: Final = 1.0
EFFECT_DELAY: Final = 0.5  # Delay after effect changes
STATUS_DELAY: Final = 0.2  # Delay after status request
TURN_OFF_DELAY: Final = 0.15  # Short delay after turn off sequence
# Wait after BLE connect before the first GATT op. Beurer firmware aborts
# the GATT subscribe ("changed connection status while waiting for
# BluetoothGATTNotifyResponse") if issued immediately after the link is
# up. The official LightUp APK pauses ~300-500ms; mirror that here.
POST_CONNECT_SETTLE: Final = 0.4

# Rate limiting for commands to prevent overwhelming the device
MIN_COMMAND_INTERVAL: Final = 0.1  # Minimum time between commands (100ms)

# Command timeout - matches Beurer LightUp APK's TimeOutRequestProxy (6000ms)
# Prevents hanging on unresponsive devices (bleak default is ~30s)
COMMAND_TIMEOUT: Final = 6.0  # Maximum wait for a single BLE write (seconds)

# Reconnection timing constants
RECONNECT_INITIAL_BACKOFF: Final = 5.0  # Initial delay before reconnect (seconds)
RECONNECT_MAX_BACKOFF: Final = (
    60.0  # Maximum backoff delay (1 min cap — reconnects within 60s after any outage)
)
RECONNECT_BACKOFF_MULTIPLIER: Final = (
    1.5  # Backoff multiplier (5→7.5→11→17→25→38→56→60s cap reached after ~7 attempts)
)
RECONNECT_MIN_INTERVAL: Final = (
    30.0  # Minimum time between reconnect attempts (seconds)
)

# Connection health monitoring
CONNECTION_WATCHDOG_INTERVAL: Final = 60.0  # Check connection health every N seconds
CONNECTION_STALE_TIMEOUT: Final = (
    300.0  # Consider connection stale after N seconds without data
)

# Adapter failure tracking
ADAPTER_FAILURE_COOLDOWN: Final = 300.0  # Cooldown for failed adapters (seconds)

# Adaptive polling intervals
# Poll more frequently when light is on for responsive updates
POLL_INTERVAL_LIGHT_ON: Final = 30  # 30 seconds when light is on
POLL_INTERVAL_LIGHT_OFF: Final = 300  # 5 minutes when light is off
POLL_INTERVAL_UNAVAILABLE: Final = 900  # 15 minutes when device unavailable

# Supported light effects (index corresponds to protocol value)
SUPPORTED_EFFECTS: Final[list[str]] = [
    "Off",  # 0
    "Random",  # 1
    "Rainbow",  # 2
    "Rainbow Slow",  # 3
    "Fusion",  # 4
    "Pulse",  # 5
    "Wave",  # 6
    "Chill",  # 7
    "Action",  # 8
    "Forest",  # 9
    "Summer",  # 10
]

# Device name prefixes for discovery (lowercase for case-insensitive matching)
DEVICE_NAME_PREFIXES: Final[tuple[str, ...]] = (
    "tl100",
    "tl50",
    "tl70",
    "tl80",
    "tl90",
    "wl_90",  # WL90 Wake-up Light (uses underscore in BLE name)
    "wl90",  # WL90 alternate naming
    "wl 90",  # WL90 pair name in Beurer LightUp
    "wl_75",  # WL75 Wake-up Light (underscore variant)
    "wl75",  # WL75 alternate naming
    "wl 75",  # WL75 pair name in Beurer LightUp
)

# Model detection map based on device name prefixes
MODEL_MAP: Final[dict[str, str]] = {
    "TL100": "TL100 Daylight Therapy Lamp",
    "TL50": "TL50 Daylight Therapy Lamp",
    "TL70": "TL70 Daylight Therapy Lamp",
    "TL80": "TL80 Daylight Therapy Lamp",
    "TL90": "TL90 Daylight Therapy Lamp",
    "WL_90": "WL90 Wake-up Light",
    "WL90": "WL90 Wake-up Light",
    "WL 90": "WL90 Wake-up Light",
    "WL_75": "WL75 Wake-up Light",
    "WL75": "WL75 Wake-up Light",
    "WL 75": "WL75 Wake-up Light",
}

# Models classification
WL90_MODELS: Final[frozenset[str]] = frozenset({"WL_90", "WL90", "WL 90"})
WL75_MODELS: Final[frozenset[str]] = frozenset({"WL_75", "WL75", "WL 75"})
WL_MODELS: Final[frozenset[str]] = WL90_MODELS | WL75_MODELS

# Timer max values differ per device model (from APK)
TIMER_MAX_WL90: Final = 60  # WL90: max 60 minutes light timer
TIMER_MAX_TL: Final = 120  # TL models: max 120 minutes light timer

# Alarm tone names (from APK resources, index 0-11)
ALARM_TONES: Final[list[str]] = [
    "Buzzer",  # 0
    "Radio",  # 1 (uses actual FM radio, no tone file)
    "Melody 1",  # 2
    "Melody 2",  # 3
    "Melody 3",  # 4
    "Melody 4",  # 5
    "Melody 5",  # 6
    "Melody 6",  # 7
    "Melody 7",  # 8
    "Melody 8",  # 9
    "Melody 9",  # 10
    "Melody 10",  # 11
]


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


def is_wl_model(name: str | None) -> bool:
    """Check if device is a WL model (WL90 or WL75).

    Args:
        name: Device name to check

    Returns:
        True if the device is a WL90 or WL75 model.
    """
    if not name:
        return False
    name_upper = name.upper()
    return any(name_upper.startswith(prefix) for prefix in WL_MODELS)


def is_wl75_model(name: str | None) -> bool:
    """Check if device is a WL75 model.

    Args:
        name: Device name to check

    Returns:
        True if the device is a WL75 model.
    """
    if not name:
        return False
    name_upper = name.upper()
    return any(name_upper.startswith(prefix) for prefix in WL75_MODELS)


def is_wl90_model(name: str | None) -> bool:
    """Check if device is a WL90 model.

    Args:
        name: Device name to check

    Returns:
        True if the device is a WL90 model.
    """
    if not name:
        return False
    name_upper = name.upper()
    return any(name_upper.startswith(prefix) for prefix in WL90_MODELS)


# Lamp events (event entity, integration triggers)
EVENT_TYPE_TIMER_FINISHED: Final = "timer_finished"
EVENT_TYPE_TIMER_CANCELLED: Final = "timer_cancelled"
EVENT_TYPE_SLEEP_TIMER_FINISHED: Final = "sleep_timer_finished"
EVENT_TYPE_SUNRISE_FINISHED: Final = "sunrise_finished"
EVENT_TYPE_SUNSET_FINISHED: Final = "sunset_finished"
LAMP_EVENT_TYPES: Final[list[str]] = [
    EVENT_TYPE_TIMER_FINISHED,
    EVENT_TYPE_TIMER_CANCELLED,
    EVENT_TYPE_SLEEP_TIMER_FINISHED,
    EVENT_TYPE_SUNRISE_FINISHED,
    EVENT_TYPE_SUNSET_FINISHED,
]


# Per-person therapy attribution
CONF_DEFAULT_THERAPY_USER = "default_therapy_user"
DEFAULT_THERAPY_USER: str | None = None
THERAPY_USER_UNKNOWN = "unknown"
EVENT_THERAPY_SESSION = "beurer_daylight_lamps_therapy_session"
THERAPY_HUB_IDENTIFIER = "therapy_hub"
