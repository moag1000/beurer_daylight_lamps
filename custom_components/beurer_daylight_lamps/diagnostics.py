"""Diagnostics support for Beurer Daylight Lamps."""
from __future__ import annotations

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
            "connected": instance.is_connected,
            "write_uuid": instance.write_uuid,
            "read_uuid": instance.read_uuid,
        },
    }
