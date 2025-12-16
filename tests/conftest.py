"""Fixtures for Beurer Daylight Lamps tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.beurer_daylight_lamps.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "custom_components.beurer_daylight_lamps.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry_data() -> dict:
    """Return mock config entry data."""
    return {
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
        CONF_NAME: "Test TL100",
    }


@pytest.fixture
def mock_ble_device() -> MagicMock:
    """Create a mock BLE device."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "TL100"
    return device


@pytest.fixture
def mock_beurer_instance() -> Generator[MagicMock, None, None]:
    """Create a mock BeurerInstance."""
    with patch(
        "custom_components.beurer_daylight_lamps.BeurerInstance"
    ) as mock_class:
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_on = True
        instance.rgb_color = (255, 255, 255)
        instance.color_brightness = 255
        instance.white_brightness = 255
        instance.effect = "Off"
        instance.color_mode = "white"
        instance.rssi = -60
        instance.available = True
        instance.is_connected = True
        instance.ble_available = True
        instance.supported_effects = [
            "Off", "Random", "Rainbow", "Rainbow Slow", "Fusion",
            "Pulse", "Wave", "Chill", "Action", "Forest", "Summer"
        ]
        instance.update = AsyncMock()
        instance.turn_on = AsyncMock()
        instance.turn_off = AsyncMock()
        instance.set_color = AsyncMock()
        instance.set_white = AsyncMock()
        instance.set_effect = AsyncMock()
        instance.set_color_brightness = AsyncMock()
        instance.connect = AsyncMock(return_value=True)
        instance.disconnect = AsyncMock()
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        instance.update_rssi = MagicMock()
        mock_class.return_value = instance
        yield instance


@pytest.fixture
def mock_discover() -> Generator[AsyncMock, None, None]:
    """Mock BLE discovery."""
    with patch(
        "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.discover"
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_get_device() -> Generator[AsyncMock, None, None]:
    """Mock get_device function."""
    with patch(
        "custom_components.beurer_daylight_lamps.get_device"
    ) as mock:
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        mock.return_value = (device, -60)  # Returns tuple (device, rssi)
        yield mock
