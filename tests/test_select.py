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
from tests.conftest import create_mock_coordinator


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


@pytest.fixture
def mock_coordinator(mock_instance: MagicMock) -> MagicMock:
    """Create a mock coordinator."""
    return create_mock_coordinator(mock_instance)


class TestBeurerEffectSelect:
    """Test the BeurerEffectSelect class."""

    def test_unique_id(self, mock_coordinator: MagicMock) -> None:
        """Test unique_id generation."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])
        expected_id = f"{format_mac(mock_coordinator.instance.mac)}_effect"
        assert select.unique_id == expected_id

    def test_options(self, mock_coordinator: MagicMock) -> None:
        """Test available options."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])
        assert select.options == list(SUPPORTED_EFFECTS)
        assert "Rainbow" in select.options
        assert "Pulse" in select.options

    def test_current_option(self, mock_coordinator: MagicMock) -> None:
        """Test current option property."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])
        assert select.current_option == "Off"

        mock_coordinator.instance.effect = "Rainbow"
        assert select.current_option == "Rainbow"

    def test_available(self, mock_coordinator: MagicMock) -> None:
        """Test availability."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])
        assert select.available is True

        mock_coordinator.instance.available = False
        assert select.available is False

    def test_instance_reference(self, mock_coordinator: MagicMock) -> None:
        """Test select correctly references instance from coordinator."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])

        assert select._instance == mock_coordinator.instance

    @pytest.mark.asyncio
    async def test_select_option(self, mock_coordinator: MagicMock) -> None:
        """Test selecting an option."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])

        await select.async_select_option("Rainbow")
        mock_coordinator.instance.set_effect.assert_called_once_with("Rainbow")

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        """Test device info."""
        select = BeurerEffectSelect(mock_coordinator, "Test Lamp", SELECT_DESCRIPTIONS[0])
        info = select.device_info

        assert info is not None
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
    async def test_creates_select_entity(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry creates select entity."""
        from custom_components.beurer_daylight_lamps.select import async_setup_entry

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

        # Should create 1 entity for effect select
        assert len(added_entities) == 1
        assert isinstance(added_entities[0], BeurerEffectSelect)

    @pytest.mark.asyncio
    async def test_uses_default_name(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.select import async_setup_entry

        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {}  # No name provided

        mock_hass = MagicMock()
        added_entities = []

        await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

        # Entity should have default name
        assert added_entities[0]._device_name == "Beurer Lamp"
