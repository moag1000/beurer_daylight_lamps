"""Diagnostics support for Beurer Daylight Lamps."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from . import BeurerConfigEntry

TO_REDACT = {CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BeurerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    instance = entry.runtime_data

    # Format last_seen as ISO timestamp
    last_seen_ts = instance.last_seen
    last_seen_str = datetime.fromtimestamp(last_seen_ts).isoformat() if last_seen_ts else None

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_state": {
            "is_on": instance.is_on,
            "color_mode": str(instance.color_mode),
            "white_brightness": instance.white_brightness,
            "color_brightness": instance.color_brightness,
            "rgb_color": instance.rgb_color,
            "effect": instance.effect,
            "supported_effects": instance.supported_effects,
            "rssi": instance.rssi,
        },
        "connection": {
            "available": instance.available,
            "ble_available": instance.ble_available,
            "connected": instance.is_connected,
            "write_uuid": instance.write_uuid,
            "read_uuid": instance.read_uuid,
            "last_seen": last_seen_str,
        },
    }
