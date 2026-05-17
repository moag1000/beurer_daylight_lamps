"""Tests for therapy user attribution (select entity)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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

        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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

        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.const import (
            CONF_DEFAULT_THERAPY_USER,
        )
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

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
        from custom_components.beurer_daylight_lamps.select import (
            BeurerTherapyUserSelect,
        )

        mock_coordinator.instance.available = False

        entity = BeurerTherapyUserSelect(
            mock_hass_no_persons, mock_coordinator, "Test Lamp", mock_entry
        )
        assert entity.available is True


# ---------------------------------------------------------------------------
# Tests for BeurerInstance._resolve_therapy_person and auto-session wiring
# ---------------------------------------------------------------------------

def _make_beurer_instance(mac: str = "AA:BB:CC:DD:EE:FF") -> BeurerInstance:  # noqa: F821
    """Construct a BeurerInstance with BleakClient mocked out."""
    from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
        BeurerInstance,
    )

    device = MagicMock()
    device.address = mac
    device.name = "TL100"
    device.rssi = -60
    return BeurerInstance(device, rssi=-60)


class TestResolveTherapyPerson:
    """Unit tests for BeurerInstance._resolve_therapy_person."""

    @pytest.fixture(autouse=True)
    def mock_bleak(self):
        """Suppress BleakClient for all tests in this class."""
        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakClient"
        ):
            yield

    def _make_instance_with_hass(
        self,
        entity_id: str | None,
        state_value: str | None,
    ) -> BeurerInstance:  # noqa: F821
        """Helper: build instance with a mock hass wired to the given entity/state."""
        instance = _make_beurer_instance()

        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.return_value = entity_id

        mock_hass = MagicMock()
        if entity_id is not None and state_value is not None:
            mock_state = MagicMock()
            mock_state.state = state_value
            mock_hass.states.get.return_value = mock_state
        else:
            mock_hass.states.get.return_value = None

        instance._hass = mock_hass

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.er.async_get",
            return_value=mock_registry,
        ):
            return instance._resolve_therapy_person()

    def test_returns_person_id_when_select_has_valid_state(self) -> None:
        """Returns the state string when the select entity has a valid person entity_id."""
        result = self._make_instance_with_hass(
            entity_id="select.test_lamp_therapy_user",
            state_value="person.michael",
        )
        assert result == "person.michael"

    def test_returns_none_when_entity_not_registered(self) -> None:
        """Returns None when the therapy_user entity is not in the entity registry."""
        result = self._make_instance_with_hass(
            entity_id=None,
            state_value=None,
        )
        assert result is None

    def test_returns_none_when_state_is_none(self) -> None:
        """Returns None when hass.states.get returns None (entity not loaded)."""
        instance = _make_beurer_instance()
        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.return_value = "select.test_lamp_therapy_user"
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None
        instance._hass = mock_hass

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.er.async_get",
            return_value=mock_registry,
        ):
            result = instance._resolve_therapy_person()

        assert result is None

    def test_returns_none_when_state_is_therapy_user_unknown(self) -> None:
        """Returns None when the select entity state is the THERAPY_USER_UNKNOWN sentinel."""
        result = self._make_instance_with_hass(
            entity_id="select.test_lamp_therapy_user",
            state_value=THERAPY_USER_UNKNOWN,
        )
        assert result is None

    def test_returns_none_when_state_is_unavailable(self) -> None:
        """Returns None when the select entity state is 'unavailable'."""
        result = self._make_instance_with_hass(
            entity_id="select.test_lamp_therapy_user",
            state_value="unavailable",
        )
        assert result is None

    def test_returns_none_when_state_is_unknown(self) -> None:
        """Returns None when the select entity state is 'unknown'."""
        result = self._make_instance_with_hass(
            entity_id="select.test_lamp_therapy_user",
            state_value="unknown",
        )
        assert result is None

    def test_unique_id_uses_formatted_mac(self) -> None:
        """The registry lookup uses format_mac(mac) + '_therapy_user' as unique_id."""
        instance = _make_beurer_instance(mac="AA:BB:CC:DD:EE:FF")
        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.return_value = None
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None
        instance._hass = mock_hass

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.er.async_get",
            return_value=mock_registry,
        ):
            instance._resolve_therapy_person()

        expected_unique_id = f"{format_mac('AA:BB:CC:DD:EE:FF')}_therapy_user"
        mock_registry.async_get_entity_id.assert_called_once_with(
            "select", DOMAIN, expected_unique_id
        )


class TestAutoSessionUsesSelectPerson:
    """Test that auto-started sessions receive the person_id from the select entity."""

    @pytest.fixture(autouse=True)
    def mock_bleak(self):
        """Suppress BleakClient for all tests in this class."""
        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakClient"
        ):
            yield

    def _drive_track_therapy(
        self,
        person_id: str | None,
        brightness: int = 230,  # ~90% -> >= 80%
        rgb: tuple[int, int, int] = (200, 200, 200),  # white-ish
    ):
        """Drive _track_therapy_from_rgb on a fresh instance with mocked dependencies."""
        instance = _make_beurer_instance()

        # Set up lamp state: color mode ON, bright white-ish
        instance._color_on = True
        instance._color_brightness = brightness
        instance._rgb_color = rgb

        # Mock therapy tracker: no active session so start_session will be triggered
        mock_tracker = MagicMock()
        mock_tracker.has_active_session = False
        instance._therapy_tracker = mock_tracker

        # Mock _resolve_therapy_person to return the desired person_id
        with patch.object(instance, "_resolve_therapy_person", return_value=person_id):
            instance._track_therapy_from_rgb()

        return mock_tracker

    def test_auto_session_uses_select_person(self) -> None:
        """start_session is called with person_id from the therapy_user select."""
        tracker = self._drive_track_therapy(person_id="person.michael")
        tracker.start_session.assert_called_once()
        _args, kwargs = tracker.start_session.call_args
        assert kwargs.get("person_id") == "person.michael"

    def test_auto_session_uses_none_when_select_is_unknown(self) -> None:
        """start_session is called with person_id=None when select returns None."""
        tracker = self._drive_track_therapy(person_id=None)
        tracker.start_session.assert_called_once()
        _args, kwargs = tracker.start_session.call_args
        assert kwargs.get("person_id") is None

    def test_no_auto_session_when_not_white_ish(self) -> None:
        """start_session is NOT called when RGB is not white-ish (e.g. saturated red)."""
        tracker = self._drive_track_therapy(
            person_id="person.michael",
            rgb=(255, 0, 0),  # saturated red — not white-ish
        )
        tracker.start_session.assert_not_called()

    def test_no_auto_session_when_brightness_too_low(self) -> None:
        """start_session is NOT called when brightness < 80%."""
        tracker = self._drive_track_therapy(
            person_id="person.michael",
            brightness=150,  # ~59% — below threshold
        )
        tracker.start_session.assert_not_called()
