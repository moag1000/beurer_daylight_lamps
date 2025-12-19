"""Test Beurer Daylight Lamps sensor entity."""
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTime, PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

from custom_components.beurer_daylight_lamps.sensor import (
    BeurerSensor,
    BeurerTherapySensor,
    SENSOR_DESCRIPTIONS,
    THERAPY_SENSOR_DESCRIPTIONS,
)


def test_sensor_descriptions() -> None:
    """Test diagnostic sensor descriptions are correctly defined."""
    # RSSI and last_notification sensors in SENSOR_DESCRIPTIONS
    assert len(SENSOR_DESCRIPTIONS) == 2

    # RSSI sensor
    rssi_desc = SENSOR_DESCRIPTIONS[0]
    assert rssi_desc.key == "rssi"
    assert rssi_desc.device_class == SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi_desc.state_class == SensorStateClass.MEASUREMENT
    assert rssi_desc.native_unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    assert rssi_desc.entity_category == EntityCategory.DIAGNOSTIC
    assert rssi_desc.entity_registry_enabled_default is False

    # Last notification sensor
    notif_desc = SENSOR_DESCRIPTIONS[1]
    assert notif_desc.key == "last_notification"
    assert notif_desc.entity_category == EntityCategory.DIAGNOSTIC


def test_therapy_sensor_descriptions() -> None:
    """Test therapy sensor descriptions are correctly defined."""
    # Therapy sensors are in separate tuple
    assert len(THERAPY_SENSOR_DESCRIPTIONS) == 3

    # Light exposure today
    today_desc = THERAPY_SENSOR_DESCRIPTIONS[0]
    assert today_desc.key == "therapy_today"
    assert today_desc.state_class == SensorStateClass.TOTAL_INCREASING
    assert today_desc.native_unit_of_measurement == UnitOfTime.MINUTES

    # Light exposure this week
    week_desc = THERAPY_SENSOR_DESCRIPTIONS[1]
    assert week_desc.key == "therapy_week"
    assert week_desc.state_class == SensorStateClass.TOTAL
    assert week_desc.native_unit_of_measurement == UnitOfTime.MINUTES

    # Daily goal progress
    progress_desc = THERAPY_SENSOR_DESCRIPTIONS[2]
    assert progress_desc.key == "therapy_progress"
    assert progress_desc.state_class == SensorStateClass.MEASUREMENT
    assert progress_desc.native_unit_of_measurement == PERCENTAGE


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


# === Therapy Sensor Tests ===


def test_therapy_sensor_today_value() -> None:
    """Test therapy sensor returns today's minutes."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.therapy_today_minutes = 15.567

    sensor = BeurerTherapySensor(
        mock_instance, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    assert sensor.native_value == 15.6  # Rounded to 1 decimal


def test_therapy_sensor_week_value() -> None:
    """Test therapy sensor returns week's minutes."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.therapy_week_minutes = 120.234

    sensor = BeurerTherapySensor(
        mock_instance, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[1]
    )

    assert sensor.native_value == 120.2  # Rounded to 1 decimal


def test_therapy_sensor_progress_value() -> None:
    """Test therapy sensor returns goal progress percentage."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.therapy_goal_progress_pct = 75

    sensor = BeurerTherapySensor(
        mock_instance, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[2]
    )

    assert sensor.native_value == 75


def test_therapy_sensor_always_available() -> None:
    """Test therapy sensor is always available (tracking persists)."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.available = False  # Device disconnected

    sensor = BeurerTherapySensor(
        mock_instance, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    # Therapy sensors are always available because tracking persists
    assert sensor.available is True


def test_therapy_sensor_unique_id() -> None:
    """Test therapy sensor unique ID generation."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"

    sensor = BeurerTherapySensor(
        mock_instance, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_therapy_today"


def test_therapy_sensor_device_info() -> None:
    """Test therapy sensor device info."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"

    sensor = BeurerTherapySensor(
        mock_instance, "Test TL100", THERAPY_SENSOR_DESCRIPTIONS[0]
    )
    device_info = sensor.device_info

    assert device_info["manufacturer"] == "Beurer"
    assert device_info["name"] == "Test TL100"
    assert ("beurer_daylight_lamps", "aa:bb:cc:dd:ee:ff") in device_info["identifiers"]
