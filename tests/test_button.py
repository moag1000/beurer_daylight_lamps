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
from tests.conftest import create_mock_coordinator


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


@pytest.fixture
def mock_coordinator(mock_instance: MagicMock) -> MagicMock:
    """Create a mock coordinator."""
    return create_mock_coordinator(mock_instance)


class TestBeurerButton:
    """Test the BeurerButton class."""

    def test_unique_id(self, mock_coordinator: MagicMock) -> None:
        """Test unique_id generation."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[0])
        expected_id = f"{format_mac(mock_coordinator.instance.mac)}_identify"
        assert button.unique_id == expected_id

    def test_identify_available(self, mock_coordinator: MagicMock) -> None:
        """Test identify button availability."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[0])
        assert button.available is True

        mock_coordinator.instance.available = False
        assert button.available is False

    def test_reconnect_always_available(self, mock_coordinator: MagicMock) -> None:
        """Test reconnect button is always available."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[1])
        assert button.available is True

        mock_coordinator.instance.available = False
        assert button.available is True  # Still available

    def test_instance_reference(self, mock_coordinator: MagicMock) -> None:
        """Test button correctly references instance from coordinator."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[0])

        assert button._instance == mock_coordinator.instance

    @pytest.mark.asyncio
    async def test_identify_press(self, mock_coordinator: MagicMock) -> None:
        """Test identify button press."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[0])

        with patch(
            "custom_components.beurer_daylight_lamps.button.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await button.async_press()

        # Should have called turn_off and turn_on multiple times
        assert mock_coordinator.instance.turn_off.call_count >= 1
        assert mock_coordinator.instance.turn_on.call_count >= 1

    @pytest.mark.asyncio
    async def test_reconnect_press(self, mock_coordinator: MagicMock) -> None:
        """Test reconnect button press."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[1])

        with patch(
            "custom_components.beurer_daylight_lamps.button.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await button.async_press()

        mock_coordinator.instance.disconnect.assert_called_once()
        mock_coordinator.instance.connect.assert_called_once()

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device info."""
        button = BeurerButton(mock_coordinator, "Test Lamp", BUTTON_DESCRIPTIONS[0])
        info = button.device_info

        assert info is not None
        assert "identifiers" in info
        assert info["manufacturer"] == "Beurer"


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
    async def test_creates_button_entities(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry creates button entities."""
        from custom_components.beurer_daylight_lamps.button import async_setup_entry

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

        # Should create 2 entities: identify and reconnect
        assert len(added_entities) == 2
        assert all(isinstance(e, BeurerButton) for e in added_entities)

    @pytest.mark.asyncio
    async def test_uses_default_name(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.button import async_setup_entry

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
