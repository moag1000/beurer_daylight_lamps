"""Diagnostics support for Beurer Daylight Lamps.

This module implements the Home Assistant diagnostics platform for Gold tier compliance.
Diagnostics allow users to download troubleshooting information about their device.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from . import BeurerConfigEntry
from .const import VERSION

# Data to redact for privacy - MAC addresses are semi-sensitive
TO_REDACT = {CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BeurerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    This provides comprehensive diagnostic information for troubleshooting
    device connectivity and state issues.
    """
    instance = entry.runtime_data.instance

    # Format timestamps as ISO strings
    last_seen_ts = instance.last_seen
    last_seen_str = datetime.fromtimestamp(last_seen_ts).isoformat() if last_seen_ts else None

    # Gather therapy tracking stats if available
    therapy_info = {}
    try:
        therapy_info = {
            "daily_goal_minutes": instance.therapy_daily_goal,
            "today_minutes": round(instance.therapy_today_minutes, 1),
            "week_minutes": round(instance.therapy_week_minutes, 1),
            "goal_progress_pct": instance.therapy_goal_progress_pct,
            "goal_reached": instance.therapy_goal_reached,
        }
    except AttributeError:
        therapy_info = {"available": False}

    # Gather sunrise/sunset simulation status
    simulation_info = {}
    try:
        sim = instance.sunrise_simulation
        simulation_info = {
            "is_running": sim.is_running if hasattr(sim, "is_running") else False,
        }
    except AttributeError:
        simulation_info = {"available": False}

    return {
        "integration_version": VERSION,
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
        "therapy_tracking": therapy_info,
        "simulation": simulation_info,
        "bluetooth_info": {
            "mac_redacted": True,
            "adapter_source": "Home Assistant Bluetooth Stack",
        },
    }
