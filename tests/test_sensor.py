"""Test Beurer Daylight Lamps sensor entity."""
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.entity import EntityCategory

from custom_components.beurer_daylight_lamps.sensor import (
    BeurerSensor,
    SENSOR_DESCRIPTIONS,
)


def test_sensor_descriptions() -> None:
    """Test sensor descriptions are correctly defined."""
    assert len(SENSOR_DESCRIPTIONS) == 1

    rssi_desc = SENSOR_DESCRIPTIONS[0]
    assert rssi_desc.key == "rssi"
    assert rssi_desc.device_class == SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi_desc.state_class == SensorStateClass.MEASUREMENT
    assert rssi_desc.native_unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    assert rssi_desc.entity_category == EntityCategory.DIAGNOSTIC
    assert rssi_desc.entity_registry_enabled_default is False


def test_sensor_unique_id() -> None:
    """Test sensor unique ID generation with normalized MAC."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = -60

    sensor = BeurerSensor(mock_instance, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    # Unique ID uses normalized (lowercase) MAC address
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_rssi"


def test_sensor_native_value() -> None:
    """Test sensor returns RSSI value."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = -65

    sensor = BeurerSensor(mock_instance, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.native_value == -65


def test_sensor_native_value_none() -> None:
    """Test sensor returns None when RSSI is None."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = None

    sensor = BeurerSensor(mock_instance, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.native_value is None


def test_sensor_available_when_connected() -> None:
    """Test sensor is available when device is connected."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = -60
    mock_instance.available = True

    sensor = BeurerSensor(mock_instance, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.available is True


def test_sensor_unavailable_when_disconnected() -> None:
    """Test sensor is unavailable when device is disconnected."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = -60
    mock_instance.available = False

    sensor = BeurerSensor(mock_instance, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.available is False


def test_sensor_device_info() -> None:
    """Test sensor device info with normalized MAC."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = -60

    sensor = BeurerSensor(mock_instance, "Test TL100", SENSOR_DESCRIPTIONS[0])
    device_info = sensor.device_info

    assert device_info["manufacturer"] == "Beurer"
    assert device_info["name"] == "Test TL100"
    # Device info uses normalized (lowercase) MAC address
    assert ("beurer_daylight_lamps", "aa:bb:cc:dd:ee:ff") in device_info["identifiers"]


def test_sensor_has_entity_name() -> None:
    """Test sensor has entity name attribute set."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.rssi = -60

    sensor = BeurerSensor(mock_instance, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor._attr_has_entity_name is True
