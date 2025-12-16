"""Tests for the Beurer number platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.device_registry import format_mac

from custom_components.beurer_daylight_lamps.number import (
    BeurerBrightnessNumber,
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
