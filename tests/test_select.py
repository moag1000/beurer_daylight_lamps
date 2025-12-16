"""Tests for the Beurer select platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.device_registry import format_mac

from custom_components.beurer_daylight_lamps.select import (
    BeurerEffectSelect,
    SELECT_DESCRIPTIONS,
)
from custom_components.beurer_daylight_lamps.const import SUPPORTED_EFFECTS


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.available = True
    instance.effect = "Off"
    instance.set_effect = AsyncMock()
    instance.set_update_callback = MagicMock()
    instance.remove_update_callback = MagicMock()
    return instance


class TestBeurerEffectSelect:
    """Test the BeurerEffectSelect class."""

    def test_unique_id(self, mock_instance: MagicMock) -> None:
        """Test unique_id generation."""
        select = BeurerEffectSelect(mock_instance, "Test Lamp", SELECT_DESCRIPTIONS[0])
        expected_id = f"{format_mac(mock_instance.mac)}_effect"
        assert select.unique_id == expected_id

    def test_options(self, mock_instance: MagicMock) -> None:
        """Test available options."""
        select = BeurerEffectSelect(mock_instance, "Test Lamp", SELECT_DESCRIPTIONS[0])
        assert select.options == list(SUPPORTED_EFFECTS)
        assert "Rainbow" in select.options
        assert "Pulse" in select.options

    def test_current_option(self, mock_instance: MagicMock) -> None:
        """Test current option property."""
        select = BeurerEffectSelect(mock_instance, "Test Lamp", SELECT_DESCRIPTIONS[0])
        assert select.current_option == "Off"
        
        mock_instance.effect = "Rainbow"
        assert select.current_option == "Rainbow"

    def test_available(self, mock_instance: MagicMock) -> None:
        """Test availability."""
        select = BeurerEffectSelect(mock_instance, "Test Lamp", SELECT_DESCRIPTIONS[0])
        assert select.available is True
        
        mock_instance.available = False
        assert select.available is False

    @pytest.mark.asyncio
    async def test_select_option(self, mock_instance: MagicMock) -> None:
        """Test selecting an option."""
        select = BeurerEffectSelect(mock_instance, "Test Lamp", SELECT_DESCRIPTIONS[0])
        
        await select.async_select_option("Rainbow")
        mock_instance.set_effect.assert_called_once_with("Rainbow")

    def test_device_info(self, mock_instance: MagicMock) -> None:
        """Test device info."""
        select = BeurerEffectSelect(mock_instance, "Test Lamp", SELECT_DESCRIPTIONS[0])
        info = select.device_info
        
        assert info is not None
        assert info["manufacturer"] == "Beurer"
