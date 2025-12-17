"""Test Beurer Daylight Lamps diagnostics."""
from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_mac(hass: HomeAssistant) -> None:
    """Test that MAC address is redacted in diagnostics."""
    mock_instance = MagicMock()
    mock_instance.is_on = True
    mock_instance.color_mode = "white"
    mock_instance.white_brightness = 255
    mock_instance.color_brightness = 200
    mock_instance.rgb_color = (255, 255, 255)
    mock_instance.effect = "Off"
    mock_instance.supported_effects = ["Off", "Rainbow"]
    mock_instance.rssi = -60
    mock_instance.available = True
    mock_instance.is_connected = True
    mock_instance.write_uuid = "write-uuid"
    mock_instance.read_uuid = "read-uuid"

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test Lamp"}
    entry.runtime_data = mock_instance
    entry.as_dict = MagicMock(return_value={
        "data": {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test Lamp"},
        "entry_id": "test_entry",
    })

    result = await async_get_config_entry_diagnostics(hass, entry)

    # MAC should be redacted
    assert result["config_entry"]["data"][CONF_MAC] == "**REDACTED**"
    # Name should not be redacted
    assert result["config_entry"]["data"][CONF_NAME] == "Test Lamp"


async def test_diagnostics_device_state(hass: HomeAssistant) -> None:
    """Test diagnostics includes device state."""
    mock_instance = MagicMock()
    mock_instance.is_on = True
    mock_instance.color_mode = "rgb"
    mock_instance.white_brightness = 128
    mock_instance.color_brightness = 200
    mock_instance.rgb_color = (255, 128, 64)
    mock_instance.effect = "Rainbow"
    mock_instance.supported_effects = ["Off", "Rainbow", "Pulse"]
    mock_instance.rssi = -55
    mock_instance.available = True
    mock_instance.is_connected = True
    mock_instance.write_uuid = "write-uuid"
    mock_instance.read_uuid = "read-uuid"

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.runtime_data = mock_instance
    entry.as_dict = MagicMock(return_value={"data": {}, "entry_id": "test_entry"})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["device_state"]["is_on"] is True
    assert result["device_state"]["color_mode"] == "rgb"
    assert result["device_state"]["white_brightness"] == 128
    assert result["device_state"]["color_brightness"] == 200
    assert result["device_state"]["rgb_color"] == (255, 128, 64)
    assert result["device_state"]["effect"] == "Rainbow"
    assert result["device_state"]["supported_effects"] == ["Off", "Rainbow", "Pulse"]
    assert result["device_state"]["rssi"] == -55


async def test_diagnostics_connection_info(hass: HomeAssistant) -> None:
    """Test diagnostics includes connection info."""
    mock_instance = MagicMock()
    mock_instance.is_on = False
    mock_instance.color_mode = "white"
    mock_instance.white_brightness = None
    mock_instance.color_brightness = None
    mock_instance.rgb_color = (0, 0, 0)
    mock_instance.effect = "Off"
    mock_instance.supported_effects = ["Off"]
    mock_instance.rssi = -70
    mock_instance.available = False
    mock_instance.is_connected = False
    mock_instance.write_uuid = None
    mock_instance.read_uuid = None

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.runtime_data = mock_instance
    entry.as_dict = MagicMock(return_value={"data": {}, "entry_id": "test_entry"})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["connection"]["available"] is False
    assert result["connection"]["connected"] is False
    assert result["connection"]["write_uuid"] is None
    assert result["connection"]["read_uuid"] is None


async def test_diagnostics_no_client(hass: HomeAssistant) -> None:
    """Test diagnostics handles missing client."""
    mock_instance = MagicMock()
    mock_instance.is_on = None
    mock_instance.color_mode = "white"
    mock_instance.white_brightness = None
    mock_instance.color_brightness = None
    mock_instance.rgb_color = (255, 255, 255)
    mock_instance.effect = "Off"
    mock_instance.supported_effects = ["Off"]
    mock_instance.rssi = None
    mock_instance.available = False
    mock_instance.is_connected = False
    mock_instance.write_uuid = None
    mock_instance.read_uuid = None

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.runtime_data = mock_instance
    entry.as_dict = MagicMock(return_value={"data": {}, "entry_id": "test_entry"})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["connection"]["available"] is False
    assert result["connection"]["connected"] is False


async def test_diagnostics_therapy_tracking(hass: HomeAssistant) -> None:
    """Test diagnostics includes therapy tracking info."""
    mock_instance = MagicMock()
    mock_instance.is_on = True
    mock_instance.color_mode = "white"
    mock_instance.white_brightness = 255
    mock_instance.color_brightness = 200
    mock_instance.rgb_color = (255, 255, 255)
    mock_instance.effect = "Off"
    mock_instance.supported_effects = ["Off"]
    mock_instance.rssi = -60
    mock_instance.available = True
    mock_instance.is_connected = True
    mock_instance.ble_available = True
    mock_instance.last_seen = 1702828800.0  # Example timestamp
    mock_instance.write_uuid = "write-uuid"
    mock_instance.read_uuid = "read-uuid"
    # Therapy tracking properties
    mock_instance.therapy_daily_goal = 30
    mock_instance.therapy_today_minutes = 15.5
    mock_instance.therapy_week_minutes = 120.0
    mock_instance.therapy_goal_progress_pct = 52
    mock_instance.therapy_goal_reached = False
    # Simulation property
    mock_sim = MagicMock()
    mock_sim.is_running = False
    mock_instance.sunrise_simulation = mock_sim

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.runtime_data = mock_instance
    entry.as_dict = MagicMock(return_value={"data": {}, "entry_id": "test_entry"})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "therapy_tracking" in result
    assert result["therapy_tracking"]["daily_goal_minutes"] == 30
    assert result["therapy_tracking"]["today_minutes"] == 15.5
    assert result["therapy_tracking"]["week_minutes"] == 120.0
    assert result["therapy_tracking"]["goal_progress_pct"] == 52
    assert result["therapy_tracking"]["goal_reached"] is False
    assert "simulation" in result
    assert result["simulation"]["is_running"] is False


async def test_diagnostics_missing_therapy_attributes(hass: HomeAssistant) -> None:
    """Test diagnostics handles missing therapy attributes gracefully."""
    mock_instance = MagicMock()
    mock_instance.is_on = True
    mock_instance.color_mode = "white"
    mock_instance.white_brightness = 255
    mock_instance.color_brightness = 200
    mock_instance.rgb_color = (255, 255, 255)
    mock_instance.effect = "Off"
    mock_instance.supported_effects = ["Off"]
    mock_instance.rssi = -60
    mock_instance.available = True
    mock_instance.is_connected = True
    mock_instance.ble_available = True
    mock_instance.last_seen = None
    mock_instance.write_uuid = "write-uuid"
    mock_instance.read_uuid = "read-uuid"
    # Simulate missing therapy attributes
    del mock_instance.therapy_daily_goal
    del mock_instance.sunrise_simulation

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.runtime_data = mock_instance
    entry.as_dict = MagicMock(return_value={"data": {}, "entry_id": "test_entry"})

    result = await async_get_config_entry_diagnostics(hass, entry)

    # Should have fallback values
    assert "therapy_tracking" in result
    assert result["therapy_tracking"].get("available") is False
    assert "simulation" in result
    assert result["simulation"].get("available") is False
