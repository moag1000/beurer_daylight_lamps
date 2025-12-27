"""Test Beurer Daylight Lamps binary sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from custom_components.beurer_daylight_lamps.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    THERAPY_BINARY_SENSOR_DESCRIPTIONS,
    BeurerBinarySensor,
    BeurerTherapyBinarySensor,
)
from tests.conftest import create_mock_coordinator


# =============================================================================
# Test Binary Sensor Descriptions
# =============================================================================


class TestBinarySensorDescriptions:
    """Tests for binary sensor entity descriptions."""

    def test_connected_sensor_description(self) -> None:
        """Test connected sensor has correct description."""
        connected_desc = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        assert connected_desc.device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert connected_desc.entity_category == EntityCategory.DIAGNOSTIC
        assert connected_desc.translation_key == "connected"

    def test_ble_available_sensor_description(self) -> None:
        """Test BLE available sensor has correct description."""
        ble_desc = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "ble_available"
        )
        assert ble_desc.device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert ble_desc.entity_category == EntityCategory.DIAGNOSTIC
        assert ble_desc.translation_key == "ble_available"

    def test_therapy_goal_sensor_description(self) -> None:
        """Test therapy goal sensor has correct description."""
        therapy_desc = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        assert therapy_desc.icon == "mdi:check-circle"
        assert therapy_desc.translation_key == "therapy_goal_reached"


# =============================================================================
# Test BeurerBinarySensor Class
# =============================================================================


class TestBeurerBinarySensor:
    """Tests for BeurerBinarySensor class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_connected = True
        instance.ble_available = True
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    def test_initialization_connected(self, mock_coordinator: MagicMock) -> None:
        """Test initialization for connected sensor."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor._instance == mock_coordinator.instance
        assert sensor._device_name == "Test Lamp"
        assert sensor.entity_description == description
        assert "aa:bb:cc:dd:ee:ff_connected" in sensor._attr_unique_id

    def test_initialization_ble_available(self, mock_coordinator: MagicMock) -> None:
        """Test initialization for BLE available sensor."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "ble_available"
        )
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert "aa:bb:cc:dd:ee:ff_ble_available" in sensor._attr_unique_id

    def test_is_on_connected_true(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns True when connected."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        mock_coordinator.instance.is_connected = True
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is True

    def test_is_on_connected_false(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns False when not connected."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        mock_coordinator.instance.is_connected = False
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is False

    def test_is_on_ble_available_true(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns True when BLE is available."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "ble_available"
        )
        mock_coordinator.instance.ble_available = True
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is True

    def test_is_on_ble_available_false(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns False when BLE is not available."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "ble_available"
        )
        mock_coordinator.instance.ble_available = False
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is False

    def test_is_on_unknown_key(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns None for unknown key."""
        from homeassistant.components.binary_sensor import BinarySensorEntityDescription

        description = BinarySensorEntityDescription(key="unknown")
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is None

    def test_available_always_true(self, mock_coordinator: MagicMock) -> None:
        """Test available is always True for connectivity sensors."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.available is True

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device info is returned correctly."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        sensor = BeurerBinarySensor(mock_coordinator, "TL100 Test", description)

        device_info = sensor.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    def test_has_entity_name(self, mock_coordinator: MagicMock) -> None:
        """Test has_entity_name is True."""
        description = next(
            d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "connected"
        )
        sensor = BeurerBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor._attr_has_entity_name is True


# =============================================================================
# Test BeurerTherapyBinarySensor Class
# =============================================================================


class TestBeurerTherapyBinarySensor:
    """Tests for BeurerTherapyBinarySensor class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.therapy_goal_reached = False
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    def test_initialization(self, mock_coordinator: MagicMock) -> None:
        """Test initialization for therapy goal sensor."""
        description = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor._instance == mock_coordinator.instance
        assert sensor._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_therapy_goal_reached" in sensor._attr_unique_id

    def test_is_on_goal_reached(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns True when goal is reached."""
        description = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        mock_coordinator.instance.therapy_goal_reached = True
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is True

    def test_is_on_goal_not_reached(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns False when goal is not reached."""
        description = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        mock_coordinator.instance.therapy_goal_reached = False
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is False

    def test_is_on_unknown_key(self, mock_coordinator: MagicMock) -> None:
        """Test is_on returns None for unknown key."""
        from homeassistant.components.binary_sensor import BinarySensorEntityDescription

        description = BinarySensorEntityDescription(key="unknown")
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.is_on is None

    def test_available_always_true(self, mock_coordinator: MagicMock) -> None:
        """Test available is always True for therapy sensor."""
        description = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor.available is True

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device info is returned correctly."""
        description = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "TL100 Therapy", description)

        device_info = sensor.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Therapy"

    def test_has_entity_name(self, mock_coordinator: MagicMock) -> None:
        """Test has_entity_name is True."""
        description = next(
            d for d in THERAPY_BINARY_SENSOR_DESCRIPTIONS if d.key == "therapy_goal_reached"
        )
        sensor = BeurerTherapyBinarySensor(mock_coordinator, "Test Lamp", description)

        assert sensor._attr_has_entity_name is True


# =============================================================================
# Test async_setup_entry
# =============================================================================


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        return instance

    @pytest.mark.asyncio
    async def test_creates_all_sensors(self, mock_instance: MagicMock) -> None:
        """Test that async_setup_entry creates all expected sensors."""
        from custom_components.beurer_daylight_lamps.binary_sensor import async_setup_entry

        mock_coordinator = create_mock_coordinator(mock_instance)
        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {"name": "Test Lamp"}

        mock_hass = MagicMock()
        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        mock_add_entities = capture_entities

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        # Should create 3 sensors: connected, ble_available, therapy_goal_reached
        assert len(added_entities) == 3

        # Verify types
        beurer_sensors = [e for e in added_entities if isinstance(e, BeurerBinarySensor)]
        therapy_sensors = [e for e in added_entities if isinstance(e, BeurerTherapyBinarySensor)]

        assert len(beurer_sensors) == 2
        assert len(therapy_sensors) == 1

    @pytest.mark.asyncio
    async def test_uses_default_name(self, mock_instance: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.binary_sensor import async_setup_entry

        mock_coordinator = create_mock_coordinator(mock_instance)
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
