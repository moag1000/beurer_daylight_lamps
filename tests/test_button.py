"""Tests for the Beurer button platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from custom_components.beurer_daylight_lamps.button import (
    BeurerButton,
    BUTTON_DESCRIPTIONS,
)


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.available = True
    instance.is_on = True
    instance.turn_on = AsyncMock()
    instance.turn_off = AsyncMock()
    instance.connect = AsyncMock(return_value=True)
    instance.disconnect = AsyncMock()
    return instance


class TestBeurerButton:
    """Test the BeurerButton class."""

    def test_unique_id(self, mock_instance: MagicMock) -> None:
        """Test unique_id generation."""
        button = BeurerButton(mock_instance, "Test Lamp", BUTTON_DESCRIPTIONS[0])
        expected_id = f"{format_mac(mock_instance.mac)}_identify"
        assert button.unique_id == expected_id

    def test_identify_available(self, mock_instance: MagicMock) -> None:
        """Test identify button availability."""
        button = BeurerButton(mock_instance, "Test Lamp", BUTTON_DESCRIPTIONS[0])
        assert button.available is True
        
        mock_instance.available = False
        assert button.available is False

    def test_reconnect_always_available(self, mock_instance: MagicMock) -> None:
        """Test reconnect button is always available."""
        button = BeurerButton(mock_instance, "Test Lamp", BUTTON_DESCRIPTIONS[1])
        assert button.available is True
        
        mock_instance.available = False
        assert button.available is True  # Still available

    @pytest.mark.asyncio
    async def test_identify_press(self, mock_instance: MagicMock) -> None:
        """Test identify button press."""
        button = BeurerButton(mock_instance, "Test Lamp", BUTTON_DESCRIPTIONS[0])

        with patch(
            "custom_components.beurer_daylight_lamps.button.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await button.async_press()

        # Should have called turn_off and turn_on multiple times
        assert mock_instance.turn_off.call_count >= 1
        assert mock_instance.turn_on.call_count >= 1

    @pytest.mark.asyncio
    async def test_reconnect_press(self, mock_instance: MagicMock) -> None:
        """Test reconnect button press."""
        button = BeurerButton(mock_instance, "Test Lamp", BUTTON_DESCRIPTIONS[1])

        with patch(
            "custom_components.beurer_daylight_lamps.button.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await button.async_press()

        mock_instance.disconnect.assert_called_once()
        mock_instance.connect.assert_called_once()

    def test_device_info(self, mock_instance: MagicMock) -> None:
        """Test device info."""
        button = BeurerButton(mock_instance, "Test Lamp", BUTTON_DESCRIPTIONS[0])
        info = button.device_info
        
        assert info is not None
        assert "identifiers" in info
        assert info["manufacturer"] == "Beurer"
