"""Tests for the Beurer binary sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.helpers.device_registry import format_mac

from custom_components.beurer_daylight_lamps.binary_sensor import (
    BeurerBinarySensor,
    BINARY_SENSOR_DESCRIPTIONS,
)


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.is_connected = True
    instance.ble_available = True
    instance.set_update_callback = MagicMock()
    instance.remove_update_callback = MagicMock()
    return instance


class TestBeurerBinarySensor:
    """Test the BeurerBinarySensor class."""

    def test_unique_id_connected(self, mock_instance: MagicMock) -> None:
        """Test unique_id for connected sensor."""
        sensor = BeurerBinarySensor(mock_instance, "Test Lamp", BINARY_SENSOR_DESCRIPTIONS[0])
        expected_id = f"{format_mac(mock_instance.mac)}_connected"
        assert sensor.unique_id == expected_id

    def test_unique_id_ble_available(self, mock_instance: MagicMock) -> None:
        """Test unique_id for ble_available sensor."""
        sensor = BeurerBinarySensor(mock_instance, "Test Lamp", BINARY_SENSOR_DESCRIPTIONS[1])
        expected_id = f"{format_mac(mock_instance.mac)}_ble_available"
        assert sensor.unique_id == expected_id

    def test_is_on_connected(self, mock_instance: MagicMock) -> None:
        """Test is_on for connected sensor."""
        sensor = BeurerBinarySensor(mock_instance, "Test Lamp", BINARY_SENSOR_DESCRIPTIONS[0])
        assert sensor.is_on is True
        
        mock_instance.is_connected = False
        assert sensor.is_on is False

    def test_is_on_ble_available(self, mock_instance: MagicMock) -> None:
        """Test is_on for ble_available sensor."""
        sensor = BeurerBinarySensor(mock_instance, "Test Lamp", BINARY_SENSOR_DESCRIPTIONS[1])
        assert sensor.is_on is True
        
        mock_instance.ble_available = False
        assert sensor.is_on is False

    def test_always_available(self, mock_instance: MagicMock) -> None:
        """Test binary sensors are always available."""
        sensor = BeurerBinarySensor(mock_instance, "Test Lamp", BINARY_SENSOR_DESCRIPTIONS[0])
        assert sensor.available is True

    def test_device_info(self, mock_instance: MagicMock) -> None:
        """Test device info."""
        sensor = BeurerBinarySensor(mock_instance, "Test Lamp", BINARY_SENSOR_DESCRIPTIONS[0])
        info = sensor.device_info
        
        assert info is not None
        assert info["manufacturer"] == "Beurer"
