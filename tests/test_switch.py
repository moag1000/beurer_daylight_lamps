"""Test Beurer Daylight Lamps switch platform."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.core import HomeAssistant, State

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
        assert adaptive_desc.icon == "mdi:brightness-auto"

    def test_number_of_descriptions(self) -> None:
        """Test correct number of switch descriptions."""
        assert len(SWITCH_DESCRIPTIONS) == 1


# =============================================================================
# Test BeurerAdaptiveLightingSwitch Class
# =============================================================================


class TestBeurerAdaptiveLightingSwitch:
    """Tests for BeurerAdaptiveLightingSwitch class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.available = True
        instance.effect = "Off"
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    @pytest.fixture
    def description(self) -> SwitchEntityDescription:
        """Return the adaptive lighting description."""
        return next(d for d in SWITCH_DESCRIPTIONS if d.key == "adaptive_lighting")

    def test_initialization(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test initialization of adaptive lighting switch."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        assert switch._instance == mock_coordinator.instance
        assert switch._entry_id == "entry_123"
        assert switch._device_name == "Test Lamp"
        assert switch.entity_description == description
        assert "aa:bb:cc:dd:ee:ff_adaptive_lighting" in switch._attr_unique_id
        assert switch._is_on is True  # Default enabled

    def test_has_entity_name(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test has_entity_name is True."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        assert switch._attr_has_entity_name is True

    def test_is_on_default(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test is_on returns True by default."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        assert switch.is_on is True

    def test_is_on_when_disabled(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test is_on returns False when disabled."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = False
        assert switch.is_on is False

    def test_available(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test available property delegates to instance."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        assert switch.available is True

        mock_coordinator.instance.available = False
        assert switch.available is False

    def test_device_info(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test device_info returns correct values."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "TL100 Test", "entry_123", description
        )

        device_info = switch.device_info
        assert device_info["manufacturer"] == "Beurer"
        assert device_info["name"] == "TL100 Test"

    def test_extra_state_attributes_no_effect(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test extra_state_attributes when no effect is active."""
        mock_coordinator.instance.effect = "Off"
        mock_coordinator.instance._therapy_active = False
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        attrs = switch.extra_state_attributes
        assert attrs["description"] == "Controls whether Adaptive Lighting can adjust this lamp"
        assert attrs["therapy_mode_active"] is False
        assert attrs["current_effect"] is None

    def test_extra_state_attributes_with_effect(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test extra_state_attributes when effect is active."""
        mock_coordinator.instance.effect = "Rainbow"
        mock_coordinator.instance._therapy_active = False
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        attrs = switch.extra_state_attributes
        assert attrs["current_effect"] == "Rainbow"

    def test_extra_state_attributes_with_therapy(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test extra_state_attributes when therapy mode is active."""
        mock_coordinator.instance.effect = "Off"
        mock_coordinator.instance._therapy_active = True
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        attrs = switch.extra_state_attributes
        assert attrs["therapy_mode_active"] is True

    def test_extra_state_attributes_no_therapy_attr(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test extra_state_attributes when instance has no _therapy_active attr."""
        mock_coordinator.instance.effect = "Off"
        # Remove _therapy_active attribute
        if hasattr(mock_coordinator.instance, '_therapy_active'):
            delattr(mock_coordinator.instance, '_therapy_active')
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        attrs = switch.extra_state_attributes
        assert attrs["therapy_mode_active"] is False

    @pytest.mark.asyncio
    async def test_async_added_to_hass_no_previous_state(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_added_to_hass with no previous state."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )

        with patch.object(switch, "async_get_last_state", return_value=None):
            await switch.async_added_to_hass()

        assert switch._is_on is True  # Stays default
        assert mock_coordinator.instance.adaptive_lighting_switch == switch

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restore_on(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_added_to_hass restores 'on' state."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = False  # Start with off

        mock_state = MagicMock(spec=State)
        mock_state.state = "on"

        with patch.object(switch, "async_get_last_state", return_value=mock_state):
            await switch.async_added_to_hass()

        assert switch._is_on is True

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restore_off(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_added_to_hass restores 'off' state."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True  # Start with on (default)

        mock_state = MagicMock(spec=State)
        mock_state.state = "off"

        with patch.object(switch, "async_get_last_state", return_value=mock_state):
            await switch.async_added_to_hass()

        assert switch._is_on is False

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_will_remove_from_hass cleans up properly."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        mock_coordinator.instance.adaptive_lighting_switch = switch

        await switch.async_will_remove_from_hass()

        assert not hasattr(mock_coordinator.instance, 'adaptive_lighting_switch')

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_no_attr(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_will_remove_from_hass when attribute doesn't exist."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        # Don't set adaptive_lighting_switch

        # Should not raise
        await switch.async_will_remove_from_hass()

    @pytest.mark.asyncio
    async def test_async_turn_on(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_turn_on enables adaptive lighting."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = False

        with patch.object(switch, "async_write_ha_state") as mock_write:
            await switch.async_turn_on()

        assert switch._is_on is True
        mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_off(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test async_turn_off disables adaptive lighting."""
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True

        with patch.object(switch, "async_write_ha_state") as mock_write:
            await switch.async_turn_off()

        assert switch._is_on is False
        mock_write.assert_called_once()


# =============================================================================
# Test should_block_adaptive_lighting
# =============================================================================


class TestShouldBlockAdaptiveLighting:
    """Tests for should_block_adaptive_lighting method."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.available = True
        instance.effect = "Off"
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    @pytest.fixture
    def description(self) -> SwitchEntityDescription:
        """Return the adaptive lighting description."""
        return next(d for d in SWITCH_DESCRIPTIONS if d.key == "adaptive_lighting")

    def test_block_when_switch_off(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test blocks when switch is off."""
        mock_coordinator.instance.effect = "Off"
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = False

        assert switch.should_block_adaptive_lighting() is True

    def test_block_when_effect_active(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test blocks when effect is active."""
        mock_coordinator.instance.effect = "Rainbow"
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True

        assert switch.should_block_adaptive_lighting() is True

    def test_block_when_therapy_active(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test blocks when therapy mode is active."""
        mock_coordinator.instance.effect = "Off"
        mock_coordinator.instance._therapy_active = True
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True

        assert switch.should_block_adaptive_lighting() is True

    def test_no_block_when_all_clear(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test doesn't block when conditions allow."""
        mock_coordinator.instance.effect = "Off"
        mock_coordinator.instance._therapy_active = False
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True

        assert switch.should_block_adaptive_lighting() is False

    def test_no_block_when_no_therapy_attr(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test doesn't block when no therapy attribute exists."""
        mock_coordinator.instance.effect = "Off"
        if hasattr(mock_coordinator.instance, '_therapy_active'):
            delattr(mock_coordinator.instance, '_therapy_active')
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True

        assert switch.should_block_adaptive_lighting() is False

    def test_block_when_effect_is_none(
        self, mock_coordinator: MagicMock, description: SwitchEntityDescription
    ) -> None:
        """Test doesn't block when effect is None."""
        mock_coordinator.instance.effect = None
        mock_coordinator.instance._therapy_active = False
        switch = BeurerAdaptiveLightingSwitch(
            mock_coordinator, "Test Lamp", "entry_123", description
        )
        switch._is_on = True

        assert switch.should_block_adaptive_lighting() is False


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

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {"name": "Test Lamp"}
        mock_entry.entry_id = "entry_123"

        mock_hass = MagicMock()
        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should create 1 entity for adaptive lighting
        assert len(added_entities) == 1
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
