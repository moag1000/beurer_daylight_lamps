"""Tests for the Beurer number platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac

from custom_components.beurer_daylight_lamps.number import (
    BeurerBrightnessNumber,
    BeurerTimerNumber,
    NUMBER_DESCRIPTIONS,
)


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.available = True
    instance.white_brightness = 255
    instance.color_brightness = 128
    instance.set_white = AsyncMock()
    instance.set_color_brightness = AsyncMock()
    instance.set_update_callback = MagicMock()
    instance.remove_update_callback = MagicMock()
    return instance


class TestBeurerBrightnessNumber:
    """Test the BeurerBrightnessNumber class."""

    def test_unique_id_white(self, mock_instance: MagicMock) -> None:
        """Test unique_id for white brightness."""
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[0])
        expected_id = f"{format_mac(mock_instance.mac)}_white_brightness"
        assert number.unique_id == expected_id

    def test_unique_id_color(self, mock_instance: MagicMock) -> None:
        """Test unique_id for color brightness."""
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[1])
        expected_id = f"{format_mac(mock_instance.mac)}_color_brightness"
        assert number.unique_id == expected_id

    def test_native_value_white(self, mock_instance: MagicMock) -> None:
        """Test native value for white brightness."""
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[0])
        # 255 / 255 * 100 = 100
        assert number.native_value == 100

    def test_native_value_color(self, mock_instance: MagicMock) -> None:
        """Test native value for color brightness."""
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[1])
        # 128 / 255 * 100 = 50.2 -> 50
        assert number.native_value == 50

    def test_native_value_none(self, mock_instance: MagicMock) -> None:
        """Test native value when brightness is None."""
        mock_instance.white_brightness = None
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[0])
        assert number.native_value is None

    @pytest.mark.asyncio
    async def test_set_white_brightness(self, mock_instance: MagicMock) -> None:
        """Test setting white brightness."""
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[0])
        
        await number.async_set_native_value(50.0)
        # 50 / 100 * 255 = 127
        mock_instance.set_white.assert_called_once_with(127)

    @pytest.mark.asyncio
    async def test_set_color_brightness(self, mock_instance: MagicMock) -> None:
        """Test setting color brightness."""
        number = BeurerBrightnessNumber(mock_instance, "Test Lamp", NUMBER_DESCRIPTIONS[1])

        await number.async_set_native_value(100.0)
        # 100 / 100 * 255 = 255
        mock_instance.set_color_brightness.assert_called_once_with(255)


@pytest.fixture
def mock_timer_instance() -> MagicMock:
    """Create a mock BeurerInstance for timer tests."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.available = True
    instance.color_mode = ColorMode.RGB
    instance.set_timer = AsyncMock(return_value=True)
    instance.set_update_callback = MagicMock()
    instance.remove_update_callback = MagicMock()
    return instance


class TestBeurerTimerNumber:
    """Test the BeurerTimerNumber class."""

    def test_unique_id(self, mock_timer_instance: MagicMock) -> None:
        """Test unique_id for timer."""
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        expected_id = f"{format_mac(mock_timer_instance.mac)}_timer"
        assert timer.unique_id == expected_id

    def test_entity_category(self, mock_timer_instance: MagicMock) -> None:
        """Test entity category is CONFIG."""
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.entity_category == EntityCategory.CONFIG

    def test_translation_key(self, mock_timer_instance: MagicMock) -> None:
        """Test translation key is set."""
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.translation_key == "timer"

    def test_native_value_initial(self, mock_timer_instance: MagicMock) -> None:
        """Test native value is None initially."""
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.native_value is None

    def test_available_in_rgb_mode(self, mock_timer_instance: MagicMock) -> None:
        """Test timer is available in RGB mode."""
        mock_timer_instance.color_mode = ColorMode.RGB
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.available is True

    def test_unavailable_in_white_mode(self, mock_timer_instance: MagicMock) -> None:
        """Test timer is unavailable in white mode."""
        mock_timer_instance.color_mode = ColorMode.WHITE
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.available is False

    def test_unavailable_when_device_unavailable(self, mock_timer_instance: MagicMock) -> None:
        """Test timer is unavailable when device is unavailable."""
        mock_timer_instance.available = False
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.available is False

    def test_min_max_values(self, mock_timer_instance: MagicMock) -> None:
        """Test min/max timer values."""
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")
        assert timer.native_min_value == 1
        assert timer.native_max_value == 240

    @pytest.mark.asyncio
    async def test_set_timer_success(self, mock_timer_instance: MagicMock) -> None:
        """Test setting timer successfully."""
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")

        await timer.async_set_native_value(30.0)
        mock_timer_instance.set_timer.assert_called_once_with(30)
        assert timer.native_value == 30.0

    @pytest.mark.asyncio
    async def test_set_timer_failure_raises(self, mock_timer_instance: MagicMock) -> None:
        """Test setting timer raises error on failure."""
        mock_timer_instance.set_timer = AsyncMock(return_value=False)
        timer = BeurerTimerNumber(mock_timer_instance, "Test Lamp")

        with pytest.raises(HomeAssistantError):
            await timer.async_set_native_value(30.0)
