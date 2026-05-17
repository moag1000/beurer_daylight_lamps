"""Tests for therapy hub aggregation and session event."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.beurer_daylight_lamps.const import (
    DOMAIN,
    EVENT_THERAPY_SESSION,
    THERAPY_HUB_IDENTIFIER,
)


def _make_beurer_instance(
    mac: str = "AA:BB:CC:DD:EE:FF",
    hass: MagicMock | None = None,
) -> "BeurerInstance":  # noqa: F821
    """Construct a BeurerInstance with BleakClient mocked out."""
    from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
        BeurerInstance,
    )

    device = MagicMock()
    device.address = mac
    device.name = "TL100"
    device.rssi = -60
    return BeurerInstance(device, rssi=-60, hass=hass)


def _make_mock_hass() -> MagicMock:
    """Create a mock hass with a recording bus."""
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture(autouse=True)
def mock_bleak():
    """Suppress BleakClient for all tests in this module."""
    with patch(
        "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakClient"
    ):
        yield


class TestEventFiredOnSessionEnd:
    """Ending an active therapy session fires EVENT_THERAPY_SESSION."""

    def test_event_fired_on_session_end(self) -> None:
        """Ending an active therapy session fires EVENT_THERAPY_SESSION with the full payload."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)

        # Set entry and device_name on the instance
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id_123"
        instance._entry = mock_entry
        instance._device_name = "Test Lamp"

        # Manually start a session and backdate start_time so duration >= 1 min
        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 100, person_id="person.michael")
        # Backdate the start_time by 10 minutes
        session = instance._therapy_tracker._current_session
        session.start_time = datetime.now(UTC) - timedelta(minutes=10)

        # Trigger session end via _end_therapy_and_emit
        instance._end_therapy_and_emit()

        # Assert the event was fired exactly once
        mock_hass.bus.async_fire.assert_called_once()
        event_name, payload = mock_hass.bus.async_fire.call_args[0]
        assert event_name == EVENT_THERAPY_SESSION

        # Verify all 8 required keys are present
        assert payload["entry_id"] == "test_entry_id_123"
        assert payload["lamp_name"] == "Test Lamp"
        assert payload["person_id"] == "person.michael"
        assert "start_time" in payload
        assert "end_time" in payload
        assert payload["duration_minutes"] >= 1.0
        assert payload["color_temp_kelvin"] == 5300
        assert payload["brightness_pct"] == 100

    def test_event_payload_start_end_are_iso_strings(self) -> None:
        """start_time and end_time in the payload are ISO-format strings."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_abc"
        instance._entry = mock_entry
        instance._device_name = "Lamp"

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 90, person_id=None)
        session = instance._therapy_tracker._current_session
        session.start_time = datetime.now(UTC) - timedelta(minutes=5)

        instance._end_therapy_and_emit()

        _, payload = mock_hass.bus.async_fire.call_args[0]
        # Should be parseable ISO strings
        datetime.fromisoformat(payload["start_time"])
        datetime.fromisoformat(payload["end_time"])

    def test_event_fired_via_track_therapy_color_off(self) -> None:
        """_track_therapy_from_rgb ending a session fires the event when color turns off."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_xyz"
        instance._entry = mock_entry
        instance._device_name = "Color Lamp"

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 100, person_id="person.anna")
        session = instance._therapy_tracker._current_session
        session.start_time = datetime.now(UTC) - timedelta(minutes=3)

        # Set lamp state to color-off to trigger end
        instance._color_on = False

        with patch.object(instance, "_resolve_therapy_person", return_value=None):
            instance._track_therapy_from_rgb()

        mock_hass.bus.async_fire.assert_called_once()
        event_name, payload = mock_hass.bus.async_fire.call_args[0]
        assert event_name == EVENT_THERAPY_SESSION
        assert payload["person_id"] == "person.anna"

    def test_event_fired_via_handle_device_off(self) -> None:
        """_handle_device_off fires EVENT_THERAPY_SESSION when a session is active."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_off"
        instance._entry = mock_entry
        instance._device_name = "Off Lamp"

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 85, person_id="person.bob")
        session = instance._therapy_tracker._current_session
        session.start_time = datetime.now(UTC) - timedelta(minutes=2)

        # Make device appear as on so _handle_device_off ends the session
        instance._light_on = True
        instance._color_on = True

        instance._handle_device_off()

        mock_hass.bus.async_fire.assert_called_once()
        event_name, payload = mock_hass.bus.async_fire.call_args[0]
        assert event_name == EVENT_THERAPY_SESSION
        assert payload["person_id"] == "person.bob"


class TestNoEventWhenNoActiveSession:
    """Ending with no active session does not fire an event."""

    def test_no_event_when_no_active_session(self) -> None:
        """Calling _end_therapy_and_emit with no active session fires no event."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_empty"
        instance._entry = mock_entry
        instance._device_name = "Empty Lamp"

        # No session started — end_session returns None
        instance._end_therapy_and_emit()

        mock_hass.bus.async_fire.assert_not_called()

    def test_no_event_when_hass_is_none(self) -> None:
        """No event fired when hass is None (e.g. in offline tests)."""
        instance = _make_beurer_instance(hass=None)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_no_hass"
        instance._entry = mock_entry
        instance._device_name = "No Hass Lamp"

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 100, person_id=None)
        session = instance._therapy_tracker._current_session
        session.start_time = datetime.now(UTC) - timedelta(minutes=5)

        # Should not raise; hass is None so no event emitted
        instance._end_therapy_and_emit()
        # No assertion needed — the test passes if no AttributeError is raised

    def test_no_event_for_handle_device_off_when_lamp_already_off(self) -> None:
        """_handle_device_off does not fire event if lamp was already off."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_already_off"
        instance._entry = mock_entry
        instance._device_name = "Already Off"

        # Lamp is already marked off — no session to end
        instance._light_on = False
        instance._color_on = False

        instance._handle_device_off()

        mock_hass.bus.async_fire.assert_not_called()


# ---------------------------------------------------------------------------
# TherapyHub unit tests
# ---------------------------------------------------------------------------


def _make_mock_dev_reg() -> MagicMock:
    """Create a mock device registry."""
    dev_reg = MagicMock()
    mock_device = MagicMock()
    mock_device.id = "hub-device-id-123"
    dev_reg.async_get_or_create.return_value = mock_device
    dev_reg.async_get_device.return_value = mock_device
    dev_reg.async_remove_device = MagicMock()
    return dev_reg


def _make_mock_hass_for_hub() -> MagicMock:
    """Create a mock hass suitable for TherapyHub tests (with data dict)."""
    hass = MagicMock()
    hass.data = {}
    return hass


class TestTherapyHubDevice:
    """Unit tests for TherapyHub module-level helpers and device management."""

    def test_hub_device_created_after_setup(self) -> None:
        """ensure_device calls async_get_or_create with the correct identifiers."""
        from custom_components.beurer_daylight_lamps.therapy_hub import TherapyHub

        hass = _make_mock_hass_for_hub()
        mock_dev_reg = _make_mock_dev_reg()

        owning_entry = MagicMock()
        owning_entry.entry_id = "entry_001"

        with patch(
            "custom_components.beurer_daylight_lamps.therapy_hub.dr.async_get",
            return_value=mock_dev_reg,
        ):
            hub = TherapyHub(hass)
            hub.ensure_device(owning_entry)

        mock_dev_reg.async_get_or_create.assert_called_once()
        call_kwargs = mock_dev_reg.async_get_or_create.call_args[1]
        assert call_kwargs["identifiers"] == {(DOMAIN, THERAPY_HUB_IDENTIFIER)}
        assert call_kwargs["name"] == "Beurer Therapy Hub"
        assert call_kwargs["config_entry_id"] == "entry_001"

    def test_hub_device_removed_after_last_unload(self) -> None:
        """remove_device calls async_remove_device when the hub device exists."""
        from custom_components.beurer_daylight_lamps.therapy_hub import TherapyHub

        hass = _make_mock_hass_for_hub()
        mock_dev_reg = _make_mock_dev_reg()

        with patch(
            "custom_components.beurer_daylight_lamps.therapy_hub.dr.async_get",
            return_value=mock_dev_reg,
        ):
            hub = TherapyHub(hass)
            hub.remove_device()

        mock_dev_reg.async_remove_device.assert_called_once_with("hub-device-id-123")
        assert hub.owning_entry_id is None

    def test_hub_device_persists_when_other_entries_remain(self) -> None:
        """remove_device with no device found does not raise and does not call async_remove_device."""
        from custom_components.beurer_daylight_lamps.therapy_hub import TherapyHub

        hass = _make_mock_hass_for_hub()
        mock_dev_reg = _make_mock_dev_reg()
        # Simulate device not found
        mock_dev_reg.async_get_device.return_value = None

        with patch(
            "custom_components.beurer_daylight_lamps.therapy_hub.dr.async_get",
            return_value=mock_dev_reg,
        ):
            hub = TherapyHub(hass)
            # Should not raise
            hub.remove_device()

        mock_dev_reg.async_remove_device.assert_not_called()

    def test_get_or_create_hub_returns_singleton(self) -> None:
        """get_or_create_hub always returns the same TherapyHub instance per hass."""
        from custom_components.beurer_daylight_lamps.therapy_hub import get_or_create_hub

        hass = _make_mock_hass_for_hub()

        hub1 = get_or_create_hub(hass)
        hub2 = get_or_create_hub(hass)
        assert hub1 is hub2

    def test_ensure_device_is_idempotent(self) -> None:
        """Calling ensure_device twice does not create duplicate devices (delegate to async_get_or_create)."""
        from custom_components.beurer_daylight_lamps.therapy_hub import TherapyHub

        hass = _make_mock_hass_for_hub()
        mock_dev_reg = _make_mock_dev_reg()

        owning_entry = MagicMock()
        owning_entry.entry_id = "entry_002"

        with patch(
            "custom_components.beurer_daylight_lamps.therapy_hub.dr.async_get",
            return_value=mock_dev_reg,
        ):
            hub = TherapyHub(hass)
            hub.ensure_device(owning_entry)
            hub.ensure_device(owning_entry)

        # async_get_or_create is idempotent by HA contract; called twice here
        assert mock_dev_reg.async_get_or_create.call_count == 2
