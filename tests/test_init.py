"""Test Beurer Daylight Lamps integration setup."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of config entry."""
    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"
    mock_device.name = "TL100"

    mock_service_info = MagicMock()
    mock_service_info.rssi = -60

    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.update = AsyncMock()
    mock_instance.disconnect = AsyncMock()
    mock_instance.set_update_callback = MagicMock()
    mock_instance._ble_available = True

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    entry = MagicMock()
    entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"}
    entry.entry_id = "test_entry_id"
    entry.runtime_data = None
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    with (
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_ble_device_from_address",
            return_value=mock_device,
        ),
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_last_service_info",
            return_value=mock_service_info,
        ),
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_register_callback",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_track_unavailable",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.beurer_daylight_lamps.BeurerInstance",
            return_value=mock_instance,
        ),
        patch(
            "custom_components.beurer_daylight_lamps.BeurerDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
    ):
        from custom_components.beurer_daylight_lamps import async_setup_entry

        result = await async_setup_entry(hass, entry)

    assert result is True
    # runtime_data is now BeurerRuntimeData with instance and coordinator
    assert entry.runtime_data.instance == mock_instance
    assert entry.runtime_data.coordinator == mock_coordinator


async def test_setup_entry_device_not_found(hass: HomeAssistant) -> None:
    """Test setup continues with placeholder device when device not found.

    Note: The integration now creates a placeholder device instead of failing,
    so it should succeed and wait for passive Bluetooth discovery.
    """
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance._ble_available = False

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    entry = MagicMock()
    entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"}
    entry.entry_id = "test_entry_id"
    entry.runtime_data = None
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    with (
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_ble_device_from_address",
            return_value=None,  # Device not found
        ),
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_register_callback",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.beurer_daylight_lamps.bluetooth.async_track_unavailable",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.beurer_daylight_lamps.BeurerInstance",
            return_value=mock_instance,
        ),
        patch(
            "custom_components.beurer_daylight_lamps.BeurerDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
    ):
        from custom_components.beurer_daylight_lamps import async_setup_entry

        # Should succeed with placeholder device
        result = await async_setup_entry(hass, entry)

    assert result is True
    # Instance should be set to unavailable initially
    assert mock_instance._ble_available is False


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading config entry."""
    mock_instance = MagicMock()
    mock_instance.disconnect = AsyncMock()

    mock_coordinator = MagicMock()
    mock_coordinator.async_shutdown = AsyncMock()

    mock_runtime_data = MagicMock()
    mock_runtime_data.instance = mock_instance
    mock_runtime_data.coordinator = mock_coordinator

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.runtime_data = mock_runtime_data

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ):
        from custom_components.beurer_daylight_lamps import async_unload_entry

        result = await async_unload_entry(hass, entry)

    assert result is True
    mock_coordinator.async_shutdown.assert_called_once()
    mock_instance.disconnect.assert_called_once()
