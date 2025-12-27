"""Test Beurer Daylight Lamps number platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.exceptions import HomeAssistantError

from custom_components.beurer_daylight_lamps.number import (
    NUMBER_DESCRIPTIONS,
    BeurerBrightnessNumber,
    BeurerTimerNumber,
    BeurerTherapyGoalNumber,
)
from tests.conftest import create_mock_coordinator


# =============================================================================
# Test BeurerBrightnessNumber Class
# =============================================================================


class TestBeurerBrightnessNumber:
    """Tests for BeurerBrightnessNumber class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.white_brightness = 200
        instance.color_brightness = 150
        instance.available = True
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        instance.set_white = AsyncMock()
        instance.set_color_brightness = AsyncMock()
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    def test_initialization_white_brightness(self, mock_coordinator: MagicMock) -> None:
        """Test initialization for white brightness."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        assert number._instance == mock_coordinator.instance
        assert number._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_white_brightness" in number._attr_unique_id

    def test_initialization_color_brightness(self, mock_coordinator: MagicMock) -> None:
        """Test initialization for color brightness."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "color_brightness")
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        assert "aa:bb:cc:dd:ee:ff_color_brightness" in number._attr_unique_id

    def test_native_value_white_brightness(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns white brightness as percentage."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        mock_coordinator.instance.white_brightness = 255  # Max brightness
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        assert number.native_value == 100

    def test_native_value_color_brightness(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns color brightness as percentage."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "color_brightness")
        mock_coordinator.instance.color_brightness = 128  # ~50%
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        assert number.native_value == 50

    def test_native_value_none(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns None when brightness is None."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        mock_coordinator.instance.white_brightness = None
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        assert number.native_value is None

    def test_available(self, mock_coordinator: MagicMock) -> None:
        """Test available property."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        assert number.available is True

        mock_coordinator.instance.available = False
        assert number.available is False

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device_info returns correct values."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_coordinator, "TL100 Test", description)

        device_info = number.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    @pytest.mark.asyncio
    async def test_async_set_native_value_white(self, mock_coordinator: MagicMock) -> None:
        """Test setting white brightness value."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        await number.async_set_native_value(50)  # 50%

        mock_coordinator.instance.set_white.assert_called_once_with(127)  # 50% of 255

    @pytest.mark.asyncio
    async def test_async_set_native_value_color(self, mock_coordinator: MagicMock) -> None:
        """Test setting color brightness value."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "color_brightness")
        number = BeurerBrightnessNumber(mock_coordinator, "Test Lamp", description)

        await number.async_set_native_value(100)  # 100%

        mock_coordinator.instance.set_color_brightness.assert_called_once_with(255)


# =============================================================================
# Test BeurerTimerNumber Class
# =============================================================================


class TestBeurerTimerNumber:
    """Tests for BeurerTimerNumber class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.available = True
        instance.color_mode = ColorMode.RGB
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        instance.set_timer = AsyncMock(return_value=True)
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    def test_initialization(self, mock_coordinator: MagicMock) -> None:
        """Test initialization of timer number."""
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")

        assert timer._instance == mock_coordinator.instance
        assert timer._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_timer" in timer._attr_unique_id

    def test_native_value_inactive(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns 0 when timer inactive."""
        mock_coordinator.instance.timer_active = False
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")
        assert timer.native_value == 0

    def test_native_value_active(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns timer minutes when active."""
        mock_coordinator.instance.timer_active = True
        mock_coordinator.instance.timer_minutes = 30
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")
        assert timer.native_value == 30

    def test_available_when_device_available(self, mock_coordinator: MagicMock) -> None:
        """Test available is True when device is available (timer works in both modes)."""
        mock_coordinator.instance.available = True
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")

        assert timer.available is True

    def test_available_when_device_unavailable(self, mock_coordinator: MagicMock) -> None:
        """Test available is False when device is unavailable."""
        mock_coordinator.instance.available = False
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")

        assert timer.available is False

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device_info returns correct values."""
        timer = BeurerTimerNumber(mock_coordinator, "TL100 Test")

        device_info = timer.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_coordinator: MagicMock) -> None:
        """Test setting timer value successfully."""
        mock_coordinator.instance.set_timer = AsyncMock(return_value=True)
        mock_coordinator.instance.timer_active = False
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")

        await timer.async_set_native_value(30)

        mock_coordinator.instance.set_timer.assert_called()

    @pytest.mark.asyncio
    async def test_async_set_native_value_failure(self, mock_coordinator: MagicMock) -> None:
        """Test setting timer value fails raises error."""
        mock_coordinator.instance.set_timer = AsyncMock(return_value=False)
        mock_coordinator.instance.timer_active = False
        timer = BeurerTimerNumber(mock_coordinator, "Test Lamp")

        with pytest.raises(HomeAssistantError, match="Failed to set timer"):
            await timer.async_set_native_value(30)


# =============================================================================
# Test BeurerTherapyGoalNumber Class
# =============================================================================


class TestBeurerTherapyGoalNumber:
    """Tests for BeurerTherapyGoalNumber class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.therapy_daily_goal = 30
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        instance.set_therapy_daily_goal = MagicMock()
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    def test_initialization(self, mock_coordinator: MagicMock) -> None:
        """Test initialization of therapy goal number."""
        goal = BeurerTherapyGoalNumber(mock_coordinator, "Test Lamp")

        assert goal._instance == mock_coordinator.instance
        assert goal._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_therapy_goal" in goal._attr_unique_id

    def test_native_value(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns therapy daily goal."""
        mock_coordinator.instance.therapy_daily_goal = 45
        goal = BeurerTherapyGoalNumber(mock_coordinator, "Test Lamp")

        assert goal.native_value == 45

    def test_available_always_true(self, mock_coordinator: MagicMock) -> None:
        """Test available is always True (configuration entity)."""
        goal = BeurerTherapyGoalNumber(mock_coordinator, "Test Lamp")

        assert goal.available is True

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device_info returns correct values."""
        goal = BeurerTherapyGoalNumber(mock_coordinator, "TL100 Test")

        device_info = goal.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    @pytest.mark.asyncio
    async def test_async_set_native_value(self, mock_coordinator: MagicMock) -> None:
        """Test setting therapy goal value."""
        goal = BeurerTherapyGoalNumber(mock_coordinator, "Test Lamp")

        await goal.async_set_native_value(45)

        mock_coordinator.instance.set_therapy_daily_goal.assert_called_once_with(45)


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

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    @pytest.mark.asyncio
    async def test_creates_all_entities(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry creates all expected entities."""
        from custom_components.beurer_daylight_lamps.number import async_setup_entry

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

        # Should create 4 entities: white_brightness, color_brightness, timer, therapy_goal
        assert len(added_entities) == 4

        # Verify types
        brightness_numbers = [e for e in added_entities if isinstance(e, BeurerBrightnessNumber)]
        timer_numbers = [e for e in added_entities if isinstance(e, BeurerTimerNumber)]
        goal_numbers = [e for e in added_entities if isinstance(e, BeurerTherapyGoalNumber)]

        assert len(brightness_numbers) == 2
        assert len(timer_numbers) == 1
        assert len(goal_numbers) == 1

    @pytest.mark.asyncio
    async def test_uses_default_name(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.number import async_setup_entry

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
