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
from tests.conftest import create_mock_coordinator


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


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.rssi = -60
    instance.available = True
    instance.last_raw_notification = "test_notification"
    instance.therapy_today_minutes = 15.567
    instance.therapy_week_minutes = 120.234
    instance.therapy_goal_progress_pct = 75
    return instance


@pytest.fixture
def mock_coordinator(mock_instance: MagicMock) -> MagicMock:
    """Create a mock coordinator."""
    return create_mock_coordinator(mock_instance)


def test_sensor_unique_id(mock_coordinator: MagicMock) -> None:
    """Test sensor unique ID generation with normalized MAC."""
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    # Unique ID uses normalized (lowercase) MAC address
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_rssi"


def test_sensor_native_value(mock_coordinator: MagicMock) -> None:
    """Test sensor returns RSSI value."""
    mock_coordinator.instance.rssi = -65
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.native_value == -65


def test_sensor_native_value_none(mock_coordinator: MagicMock) -> None:
    """Test sensor returns None when RSSI is None."""
    mock_coordinator.instance.rssi = None
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.native_value is None


def test_sensor_available_when_connected(mock_coordinator: MagicMock) -> None:
    """Test sensor is available when device is connected."""
    mock_coordinator.instance.available = True
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.available is True


def test_sensor_unavailable_when_disconnected(mock_coordinator: MagicMock) -> None:
    """Test sensor is unavailable when device is disconnected."""
    mock_coordinator.instance.available = False
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor.available is False


def test_sensor_device_info(mock_coordinator: MagicMock) -> None:
    """Test sensor device info with normalized MAC."""
    sensor = BeurerSensor(mock_coordinator, "Test TL100", SENSOR_DESCRIPTIONS[0])
    device_info = sensor.device_info

    assert device_info["manufacturer"] == "Beurer"
    assert device_info["name"] == "Test TL100"
    # Device info uses normalized (lowercase) MAC address
    assert ("beurer_daylight_lamps", "aa:bb:cc:dd:ee:ff") in device_info["identifiers"]


def test_sensor_has_entity_name(mock_coordinator: MagicMock) -> None:
    """Test sensor has entity name attribute set."""
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor._attr_has_entity_name is True


def test_sensor_instance_reference(mock_coordinator: MagicMock) -> None:
    """Test sensor correctly references instance from coordinator."""
    sensor = BeurerSensor(mock_coordinator, "Test Lamp", SENSOR_DESCRIPTIONS[0])

    assert sensor._instance == mock_coordinator.instance


# === Therapy Sensor Tests ===


def test_therapy_sensor_today_value(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor returns today's minutes."""
    mock_coordinator.instance.therapy_today_minutes = 15.567
    sensor = BeurerTherapySensor(
        mock_coordinator, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    assert sensor.native_value == 15.6  # Rounded to 1 decimal


def test_therapy_sensor_week_value(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor returns week's minutes."""
    mock_coordinator.instance.therapy_week_minutes = 120.234
    sensor = BeurerTherapySensor(
        mock_coordinator, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[1]
    )

    assert sensor.native_value == 120.2  # Rounded to 1 decimal


def test_therapy_sensor_progress_value(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor returns goal progress percentage."""
    mock_coordinator.instance.therapy_goal_progress_pct = 75
    sensor = BeurerTherapySensor(
        mock_coordinator, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[2]
    )

    assert sensor.native_value == 75


def test_therapy_sensor_always_available(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor is always available (tracking persists)."""
    mock_coordinator.instance.available = False  # Device disconnected

    sensor = BeurerTherapySensor(
        mock_coordinator, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    # Therapy sensors are always available because tracking persists
    assert sensor.available is True


def test_therapy_sensor_unique_id(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor unique ID generation."""
    sensor = BeurerTherapySensor(
        mock_coordinator, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_therapy_today"


def test_therapy_sensor_device_info(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor device info."""
    sensor = BeurerTherapySensor(
        mock_coordinator, "Test TL100", THERAPY_SENSOR_DESCRIPTIONS[0]
    )
    device_info = sensor.device_info

    assert device_info["manufacturer"] == "Beurer"
    assert device_info["name"] == "Test TL100"
    assert ("beurer_daylight_lamps", "aa:bb:cc:dd:ee:ff") in device_info["identifiers"]


def test_therapy_sensor_instance_reference(mock_coordinator: MagicMock) -> None:
    """Test therapy sensor correctly references instance from coordinator."""
    sensor = BeurerTherapySensor(
        mock_coordinator, "Test Lamp", THERAPY_SENSOR_DESCRIPTIONS[0]
    )

    assert sensor._instance == mock_coordinator.instance


# === async_setup_entry Tests ===


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    @pytest.mark.asyncio
    async def test_creates_all_entities(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry creates all expected entities."""
        from custom_components.beurer_daylight_lamps.sensor import async_setup_entry

        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {"name": "Test Lamp"}

        mock_hass = MagicMock()
        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should create 8 entities: 2 diagnostic + 3 therapy + 3 connection health
        assert len(added_entities) == 8

        # Verify types
        diagnostic_sensors = [e for e in added_entities if isinstance(e, BeurerSensor)]
        therapy_sensors = [e for e in added_entities if isinstance(e, BeurerTherapySensor)]

        assert len(diagnostic_sensors) == 2
        assert len(therapy_sensors) == 3
        # 3 connection health sensors are the remaining entities

    @pytest.mark.asyncio
    async def test_uses_default_name(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.sensor import async_setup_entry

        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {}  # No name provided

        mock_hass = MagicMock()
        added_entities = []

        await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

        # All entities should have default name
        for entity in added_entities:
            assert entity._device_name == "Beurer Lamp"
