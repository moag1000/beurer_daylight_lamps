"""Test Beurer Daylight Lamps integration setup."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.const import DOMAIN


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of config entry."""
    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"
    mock_device.name = "TL100"

    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.update = AsyncMock()
    mock_instance.disconnect = AsyncMock()
    mock_instance.set_update_callback = MagicMock()

    entry = MagicMock()
    entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"}
    entry.entry_id = "test_entry_id"

    with (
        patch(
            "custom_components.beurer_daylight_lamps.get_device",
            return_value=mock_device,
        ),
        patch(
            "custom_components.beurer_daylight_lamps.BeurerInstance",
            return_value=mock_instance,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
    ):
        from custom_components.beurer_daylight_lamps import async_setup_entry

        result = await async_setup_entry(hass, entry)

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_device_not_found(hass: HomeAssistant) -> None:
    """Test setup fails when device not found."""
    entry = MagicMock()
    entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"}
    entry.entry_id = "test_entry_id"

    with patch(
        "custom_components.beurer_daylight_lamps.get_device",
        return_value=None,
    ):
        from custom_components.beurer_daylight_lamps import async_setup_entry
        from homeassistant.exceptions import ConfigEntryNotReady

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading config entry."""
    mock_instance = MagicMock()
    mock_instance.disconnect = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test_entry_id"

    hass.data[DOMAIN] = {entry.entry_id: mock_instance}

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ):
        from custom_components.beurer_daylight_lamps import async_unload_entry

        result = await async_unload_entry(hass, entry)

    assert result is True
    mock_instance.disconnect.assert_called_once()
    assert entry.entry_id not in hass.data[DOMAIN]
