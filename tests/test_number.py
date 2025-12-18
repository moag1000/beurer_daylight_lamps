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

    def test_initialization_white_brightness(self, mock_instance: MagicMock) -> None:
        """Test initialization for white brightness."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        assert number._instance == mock_instance
        assert number._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_white_brightness" in number._attr_unique_id

    def test_initialization_color_brightness(self, mock_instance: MagicMock) -> None:
        """Test initialization for color brightness."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "color_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        assert "aa:bb:cc:dd:ee:ff_color_brightness" in number._attr_unique_id

    def test_native_value_white_brightness(self, mock_instance: MagicMock) -> None:
        """Test native_value returns white brightness as percentage."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        mock_instance.white_brightness = 255  # Max brightness
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        assert number.native_value == 100

    def test_native_value_color_brightness(self, mock_instance: MagicMock) -> None:
        """Test native_value returns color brightness as percentage."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "color_brightness")
        mock_instance.color_brightness = 128  # ~50%
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        assert number.native_value == 50

    def test_native_value_none(self, mock_instance: MagicMock) -> None:
        """Test native_value returns None when brightness is None."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        mock_instance.white_brightness = None
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        assert number.native_value is None

    def test_available(self, mock_instance: MagicMock) -> None:
        """Test available property."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        assert number.available is True

        mock_instance.available = False
        assert number.available is False

    def test_device_info(self, mock_instance: MagicMock) -> None:
        """Test device_info returns correct values."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "TL100 Test", description)

        device_info = number.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, mock_instance: MagicMock) -> None:
        """Test callback is registered when added to hass."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        await number.async_added_to_hass()

        mock_instance.set_update_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(self, mock_instance: MagicMock) -> None:
        """Test callback is removed when removed from hass."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        await number.async_will_remove_from_hass()

        mock_instance.remove_update_callback.assert_called_once()

    def test_handle_update_writes_state(self, mock_instance: MagicMock) -> None:
        """Test _handle_update writes HA state."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        with patch.object(number, "async_write_ha_state") as mock_write:
            number._handle_update()
            mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value_white(self, mock_instance: MagicMock) -> None:
        """Test setting white brightness value."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "white_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        await number.async_set_native_value(50)  # 50%

        mock_instance.set_white.assert_called_once_with(127)  # 50% of 255

    @pytest.mark.asyncio
    async def test_async_set_native_value_color(self, mock_instance: MagicMock) -> None:
        """Test setting color brightness value."""
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "color_brightness")
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", description)

        await number.async_set_native_value(100)  # 100%

        mock_instance.set_color_brightness.assert_called_once_with(255)


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

    def test_initialization(self, mock_instance: MagicMock) -> None:
        """Test initialization of timer number."""
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        assert timer._instance == mock_instance
        assert timer._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_timer" in timer._attr_unique_id
        assert timer._last_set_value is None

    def test_native_value_initial(self, mock_instance: MagicMock) -> None:
        """Test native_value returns None initially."""
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")
        assert timer.native_value is None

    def test_native_value_after_set(self, mock_instance: MagicMock) -> None:
        """Test native_value returns last set value."""
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")
        timer._last_set_value = 30
        assert timer.native_value == 30

    def test_available_in_rgb_mode(self, mock_instance: MagicMock) -> None:
        """Test available is True in RGB mode."""
        mock_instance.color_mode = ColorMode.RGB
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        assert timer.available is True

    def test_available_in_white_mode(self, mock_instance: MagicMock) -> None:
        """Test available is False in white mode (timer only works in RGB)."""
        mock_instance.color_mode = ColorMode.WHITE
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        assert timer.available is False

    def test_available_when_device_unavailable(self, mock_instance: MagicMock) -> None:
        """Test available is False when device is unavailable."""
        mock_instance.available = False
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        assert timer.available is False

    def test_device_info(self, mock_instance: MagicMock) -> None:
        """Test device_info returns correct values."""
        timer = BeurerTimerNumber(mock_instance, "TL100 Test")

        device_info = timer.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, mock_instance: MagicMock) -> None:
        """Test callback is registered when added to hass."""
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        await timer.async_added_to_hass()

        mock_instance.set_update_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(self, mock_instance: MagicMock) -> None:
        """Test callback is removed when removed from hass."""
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        await timer.async_will_remove_from_hass()

        mock_instance.remove_update_callback.assert_called_once()

    def test_handle_update_writes_state(self, mock_instance: MagicMock) -> None:
        """Test _handle_update writes HA state."""
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        with patch.object(timer, "async_write_ha_state") as mock_write:
            timer._handle_update()
            mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value_success(self, mock_instance: MagicMock) -> None:
        """Test setting timer value successfully."""
        mock_instance.set_timer = AsyncMock(return_value=True)
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

        await timer.async_set_native_value(30)

        mock_instance.set_timer.assert_called_once_with(30)
        assert timer._last_set_value == 30

    @pytest.mark.asyncio
    async def test_async_set_native_value_failure(self, mock_instance: MagicMock) -> None:
        """Test setting timer value fails raises error."""
        mock_instance.set_timer = AsyncMock(return_value=False)
        timer = BeurerTimerNumber(mock_instance, "Test Lamp")

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

    def test_initialization(self, mock_instance: MagicMock) -> None:
        """Test initialization of therapy goal number."""
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        assert goal._instance == mock_instance
        assert goal._device_name == "Test Lamp"
        assert "aa:bb:cc:dd:ee:ff_therapy_goal" in goal._attr_unique_id

    def test_native_value(self, mock_instance: MagicMock) -> None:
        """Test native_value returns therapy daily goal."""
        mock_instance.therapy_daily_goal = 45
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        assert goal.native_value == 45

    def test_available_always_true(self, mock_instance: MagicMock) -> None:
        """Test available is always True (configuration entity)."""
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        assert goal.available is True

    def test_device_info(self, mock_instance: MagicMock) -> None:
        """Test device_info returns correct values."""
        goal = BeurerTherapyGoalNumber(mock_instance, "TL100 Test")

        device_info = goal.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, mock_instance: MagicMock) -> None:
        """Test callback is registered when added to hass."""
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        await goal.async_added_to_hass()

        mock_instance.set_update_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(self, mock_instance: MagicMock) -> None:
        """Test callback is removed when removed from hass."""
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        await goal.async_will_remove_from_hass()

        mock_instance.remove_update_callback.assert_called_once()

    def test_handle_update_writes_state(self, mock_instance: MagicMock) -> None:
        """Test _handle_update writes HA state."""
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        with patch.object(goal, "async_write_ha_state") as mock_write:
            goal._handle_update()
            mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value(self, mock_instance: MagicMock) -> None:
        """Test setting therapy goal value."""
        goal = BeurerTherapyGoalNumber(mock_instance, "Test Lamp")

        await goal.async_set_native_value(45)

        mock_instance.set_therapy_daily_goal.assert_called_once_with(45)


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
    async def test_creates_all_entities(self, mock_instance: MagicMock) -> None:
        """Test that async_setup_entry creates all expected entities."""
        from custom_components.beurer_daylight_lamps.number import async_setup_entry

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_instance
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
    async def test_uses_default_name(self, mock_instance: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.number import async_setup_entry

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_instance
        mock_entry.data = {}  # No name provided

        mock_hass = MagicMock()
        added_entities = []

        await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

        # All entities should have default name
        for entity in added_entities:
            assert entity._device_name == "Beurer Lamp"
