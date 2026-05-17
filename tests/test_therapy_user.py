"""Tests for therapy user attribution (select entity)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import BaseCoordinatorEntity

from custom_components.beurer_daylight_lamps.const import (
    DOMAIN,
    THERAPY_USER_UNKNOWN,
)
from tests.conftest import create_mock_coordinator


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.available = True
    instance.effect = "Off"
    instance.set_update_callback = MagicMock()
    instance.remove_update_callback = MagicMock()
    return instance


@pytest.fixture
def mock_coordinator(mock_instance: MagicMock) -> MagicMock:
    """Create a mock coordinator."""
    return create_mock_coordinator(mock_instance)


@pytest.fixture
def mock_hass_no_persons() -> MagicMock:
    """Create a mock hass with no person states."""
    hass = MagicMock()
    hass.states.async_all.return_value = []
    return hass


@pytest.fixture
def mock_hass_with_persons() -> MagicMock:
    """Create a mock hass with two person states."""
    hass = MagicMock()
    person_anna = MagicMock()
    person_anna.entity_id = "person.anna"
    person_michael = MagicMock()
    person_michael.entity_id = "person.michael"
    hass.states.async_all.return_value = [person_anna, person_michael]
    return hass


@pytest.fixture
def mock_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {"name": "Test Lamp"}
    entry.options = {}
    return entry


class TestBeurerTherapyUserSelectCreation:
    """Test that BeurerTherapyUserSelect entity is created."""

    @pytest.mark.asyncio
    async def test_therapy_user_select_created_by_setup_entry(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """async_setup_entry creates a BeurerTherapyUserSelect alongside effect select."""
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
            async_setup_entry,
        )

        added_entities = []
        await async_setup_entry(mock_hass_no_persons, mock_entry, added_entities.extend)

        therapy_selects = [
            e for e in added_entities if isinstance(e, BeurerTherapyUserSelect)
        ]
        assert len(therapy_selects) == 1

    @pytest.mark.asyncio
    async def test_setup_entry_creates_two_entities(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """async_setup_entry creates exactly two select entities (effect + therapy_user)."""
        from custom_components.beurer_daylight_lamps.select import async_setup_entry

        added_entities = []
        await async_setup_entry(mock_hass_no_persons, mock_entry, added_entities.extend)

        assert len(added_entities) == 2


class TestBeurerTherapyUserSelectUniqueId:
    """Test unique_id generation for BeurerTherapyUserSelect."""

    def test_unique_id_ends_with_therapy_user(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Unique ID must end with '_therapy_user' (matches entity registry filter)."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        expected = f"{format_mac(mock_coordinator.instance.mac)}_therapy_user"
        assert entity.unique_id == expected


class TestBeurerTherapyUserSelectDefaultState:
    """Test default state and options for BeurerTherapyUserSelect."""

    def test_default_option_is_unknown_sentinel(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Default current_option is THERAPY_USER_UNKNOWN when no previous state."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        assert entity.current_option == THERAPY_USER_UNKNOWN

    def test_options_always_starts_with_unknown(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Options list always starts with THERAPY_USER_UNKNOWN sentinel."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        assert entity.options[0] == THERAPY_USER_UNKNOWN
        assert THERAPY_USER_UNKNOWN in entity.options

    def test_options_with_no_persons_only_unknown(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """When no HA person entities exist, options contains only the unknown sentinel."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        assert entity.options == [THERAPY_USER_UNKNOWN]

    def test_options_includes_person_entities(
        self,
        mock_coordinator: MagicMock,
        mock_hass_with_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Options includes all HA person entity_ids in sorted order after unknown."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_with_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        options = entity.options
        assert options[0] == THERAPY_USER_UNKNOWN
        assert "person.anna" in options
        assert "person.michael" in options
        # Persons are sorted
        assert options.index("person.anna") < options.index("person.michael")


class TestBeurerTherapyUserSelectOption:
    """Test option selection for BeurerTherapyUserSelect."""

    @pytest.mark.asyncio
    async def test_select_option_updates_current(
        self,
        mock_coordinator: MagicMock,
        mock_hass_with_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Selecting a valid option updates current_option."""
        from unittest.mock import patch as _patch

        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_with_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        entity.hass = mock_hass_with_persons

        # async_write_ha_state requires a full HA platform context; mock it out
        with _patch.object(entity, "async_write_ha_state"):
            await entity.async_select_option("person.anna")

        assert entity.current_option == "person.anna"

    @pytest.mark.asyncio
    async def test_select_unknown_resets_to_unknown(
        self,
        mock_coordinator: MagicMock,
        mock_hass_with_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Selecting THERAPY_USER_UNKNOWN resets the current option."""
        from unittest.mock import patch as _patch

        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_with_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        entity.hass = mock_hass_with_persons

        with _patch.object(entity, "async_write_ha_state"):
            await entity.async_select_option("person.anna")
            await entity.async_select_option(THERAPY_USER_UNKNOWN)

        assert entity.current_option == THERAPY_USER_UNKNOWN

    @pytest.mark.asyncio
    async def test_select_invalid_option_raises(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Selecting an invalid option raises HomeAssistantError."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        entity.hass = mock_hass_no_persons

        with pytest.raises(HomeAssistantError, match="Invalid therapy user"):
            await entity.async_select_option("person.does_not_exist")


class TestBeurerTherapyUserSelectRestoreState:
    """Test RestoreEntity behaviour for BeurerTherapyUserSelect."""

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restores_valid_state(
        self,
        mock_coordinator: MagicMock,
        mock_hass_with_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """If last state is a valid option, it is restored on startup."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_with_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        entity.hass = mock_hass_with_persons

        last_state = MagicMock()
        last_state.state = "person.anna"

        # Patch async_get_last_state to return a saved state
        entity.async_get_last_state = AsyncMock(return_value=last_state)

        from unittest.mock import patch as _patch

        with _patch.object(
            BaseCoordinatorEntity,
            "async_added_to_hass",
            new=AsyncMock(),
        ):
            await entity.async_added_to_hass()

        assert entity.current_option == "person.anna"

    @pytest.mark.asyncio
    async def test_async_added_to_hass_falls_back_to_default_option(
        self,
        mock_coordinator: MagicMock,
        mock_hass_with_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """If no saved state but options default set, it is applied."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect
        from custom_components.beurer_daylight_lamps.const import CONF_DEFAULT_THERAPY_USER

        mock_entry.options = {CONF_DEFAULT_THERAPY_USER: "person.michael"}

        entity = BeurerTherapyUserSelect(
            mock_hass_with_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        entity.hass = mock_hass_with_persons
        entity.async_get_last_state = AsyncMock(return_value=None)

        from unittest.mock import patch as _patch

        with _patch.object(
            BaseCoordinatorEntity,
            "async_added_to_hass",
            new=AsyncMock(),
        ):
            await entity.async_added_to_hass()

        assert entity.current_option == "person.michael"

    @pytest.mark.asyncio
    async def test_async_added_to_hass_unknown_state_ignored(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """If restored state is not in current options list, stay at UNKNOWN."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        entity.hass = mock_hass_no_persons

        last_state = MagicMock()
        last_state.state = "person.someone_deleted"  # not in options
        entity.async_get_last_state = AsyncMock(return_value=last_state)

        from unittest.mock import patch as _patch

        with _patch.object(
            BaseCoordinatorEntity,
            "async_added_to_hass",
            new=AsyncMock(),
        ):
            await entity.async_added_to_hass()

        assert entity.current_option == THERAPY_USER_UNKNOWN


class TestBeurerTherapyUserSelectDeviceInfo:
    """Test device info for BeurerTherapyUserSelect."""

    def test_device_info_manufacturer_is_beurer(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Device info manufacturer is Beurer."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        info = entity.device_info
        assert info["manufacturer"] == "Beurer"

    def test_device_info_identifiers_use_domain(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Device info identifiers use the integration domain."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        info = entity.device_info
        identifier_domains = {i[0] for i in info["identifiers"]}
        assert DOMAIN in identifier_domains


class TestBeurerTherapyUserSelectAvailability:
    """Test that BeurerTherapyUserSelect is always available."""

    def test_available_is_true_even_when_lamp_offline(
        self,
        mock_coordinator: MagicMock,
        mock_hass_no_persons: MagicMock,
        mock_entry: MagicMock,
    ) -> None:
        """Entity must remain available when the lamp is unreachable (HA-side state)."""
        from custom_components.beurer_daylight_lamps.select import BeurerTherapyUserSelect

        mock_coordinator.instance.available = False

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        assert entity.available is True
