"""Test Beurer Daylight Lamps switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.beurer_daylight_lamps.switch import (
    SWITCH_DESCRIPTIONS,
    BeurerAdaptiveLightingSwitch,
    async_setup_entry,
)
from tests.conftest import create_mock_coordinator

# =============================================================================
# Test Switch Descriptions
# =============================================================================


class TestSwitchDescriptions:
    """Tests for switch entity descriptions."""

    def test_adaptive_lighting_description(self) -> None:
        """Test adaptive lighting switch has correct description."""
        adaptive_desc = next(
            d for d in SWITCH_DESCRIPTIONS if d.key == "adaptive_lighting"
        )
        assert adaptive_desc.translation_key == "adaptive_lighting"
        assert adaptive_desc.icon is None  # icon comes from icons.json

    def test_number_of_descriptions(self) -> None:
        """Test correct number of switch descriptions."""
        # SWITCH_DESCRIPTIONS only contains adaptive_lighting (1)
        # DEVICE_SWITCH_DESCRIPTIONS contains feedback_sound and fade (2)
        # Total entities created by async_setup_entry = 3
        assert len(SWITCH_DESCRIPTIONS) == 1


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
    async def test_creates_switch_entity(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry creates switch entity."""
        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator
        mock_runtime_data.instance.is_wl = False
        mock_runtime_data.instance.is_wl75 = False

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {"name": "Test Lamp"}
        mock_entry.entry_id = "entry_123"

        mock_hass = MagicMock()
        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should create 3 entities: adaptive_lighting + feedback_sound + fade
        assert len(added_entities) == 3
        assert isinstance(added_entities[0], BeurerAdaptiveLightingSwitch)

    @pytest.mark.asyncio
    async def test_uses_default_name(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {}  # No name provided
        mock_entry.entry_id = "entry_123"

        mock_hass = MagicMock()
        added_entities = []

        await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

        # Entity should have default name
        assert added_entities[0]._device_name == "Beurer Lamp"

    @pytest.mark.asyncio
    async def test_uses_entry_id(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry passes entry_id to switch."""
        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {"name": "Test Lamp"}
        mock_entry.entry_id = "unique_entry_id_123"

        mock_hass = MagicMock()
        added_entities = []

        await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

        assert added_entities[0]._entry_id == "unique_entry_id_123"
