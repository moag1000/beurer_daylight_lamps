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
) -> BeurerInstance:  # noqa: F821
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
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            get_or_create_hub,
        )

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

    def test_ensure_device_returns_none_for_unknown_entry(self) -> None:
        """ensure_device returns None (and does not raise) when the config entry is
        not registered with HA — as happens with bare MagicMock entries in tests."""
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.beurer_daylight_lamps.therapy_hub import TherapyHub

        hass = _make_mock_hass_for_hub()
        mock_dev_reg = _make_mock_dev_reg()
        # Simulate HA refusing to link an unregistered config entry
        mock_dev_reg.async_get_or_create.side_effect = HomeAssistantError(
            "Can't link device to unknown config entry fake_id"
        )

        owning_entry = MagicMock()
        owning_entry.entry_id = "fake_id"

        with patch(
            "custom_components.beurer_daylight_lamps.therapy_hub.dr.async_get",
            return_value=mock_dev_reg,
        ):
            hub = TherapyHub(hass)
            result = hub.ensure_device(owning_entry)

        assert result is None
        # owning_entry_id should NOT be updated when the call failed
        assert hub.owning_entry_id is None


# ---------------------------------------------------------------------------
# Aggregation helper tests
# ---------------------------------------------------------------------------


def _make_session(
    person_id: str | None,
    is_therapy: bool,
    start_offset_minutes: float,
    duration_minutes: float = 10.0,
) -> MagicMock:
    """Build a mock TherapySession."""
    session = MagicMock()
    session.person_id = person_id
    session.is_therapy_light = is_therapy
    session.start_time = datetime.now(UTC) - timedelta(minutes=start_offset_minutes)
    session.duration_minutes = duration_minutes
    return session


def _make_tracker(
    sessions: list,
    current_session: MagicMock | None = None,
) -> MagicMock:
    """Build a mock TherapyTracker."""
    tracker = MagicMock()
    tracker.sessions = sessions
    tracker._current_session = current_session
    return tracker


def _make_entry_with_tracker(tracker: MagicMock) -> MagicMock:
    """Build a mock config entry whose runtime_data.instance.therapy_tracker is tracker."""
    entry = MagicMock()
    entry.runtime_data.instance.therapy_tracker = tracker
    return entry


def _make_hass_with_entries(entries: list) -> MagicMock:
    """Build a mock hass whose config_entries.async_entries(DOMAIN) returns entries."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_entries.return_value = entries
    return hass


class TestAggregationHelpers:
    """Unit tests for therapy_hub aggregation pure functions."""

    def test_today_minutes_for_aggregates_across_lamps(self) -> None:
        """today_minutes_for sums qualifying sessions for one person across all entries."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            today_minutes_for,
        )

        # Two lamps, each with one session for person.alice today
        s1 = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=60,
            duration_minutes=15.0,
        )
        s2 = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=30,
            duration_minutes=20.0,
        )
        tracker1 = _make_tracker([s1])
        tracker2 = _make_tracker([s2])
        entry1 = _make_entry_with_tracker(tracker1)
        entry2 = _make_entry_with_tracker(tracker2)
        hass = _make_hass_with_entries([entry1, entry2])

        result = today_minutes_for(hass, "person.alice")

        assert result == 35.0

    def test_today_minutes_for_only_today(self) -> None:
        """Sessions from yesterday are excluded."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            today_minutes_for,
        )

        # Session started 26 hours ago (yesterday)
        yesterday_session = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=26 * 60,
            duration_minutes=10.0,
        )
        tracker = _make_tracker([yesterday_session])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        result = today_minutes_for(hass, "person.alice")

        assert result == 0.0

    def test_today_minutes_for_only_qualifying(self) -> None:
        """Sessions that are not is_therapy_light are excluded."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            today_minutes_for,
        )

        # Not therapy light (is_therapy_light=False)
        non_therapy = _make_session(
            "person.alice",
            is_therapy=False,
            start_offset_minutes=60,
            duration_minutes=15.0,
        )
        tracker = _make_tracker([non_therapy])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        result = today_minutes_for(hass, "person.alice")

        assert result == 0.0

    def test_today_minutes_for_only_matching_person(self) -> None:
        """Sessions for other persons are excluded."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            today_minutes_for,
        )

        alice_session = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=60,
            duration_minutes=15.0,
        )
        bob_session = _make_session(
            "person.bob",
            is_therapy=True,
            start_offset_minutes=60,
            duration_minutes=20.0,
        )
        tracker = _make_tracker([alice_session, bob_session])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        result = today_minutes_for(hass, "person.alice")

        assert result == 15.0

    def test_today_minutes_for_includes_active_session(self) -> None:
        """The current (in-progress) session counts if it qualifies."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            today_minutes_for,
        )

        active = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=5,
            duration_minutes=5.0,
        )
        tracker = _make_tracker([], current_session=active)
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        result = today_minutes_for(hass, "person.alice")

        assert result == 5.0

    def test_week_minutes_for_includes_whole_week(self) -> None:
        """week_minutes_for sums sessions from the start of the current week."""
        from custom_components.beurer_daylight_lamps.therapy_hub import week_minutes_for

        # Session 3 days ago (this week)
        this_week = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=3 * 24 * 60,
            duration_minutes=30.0,
        )
        # Session 8 days ago (last week)
        last_week = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=8 * 24 * 60,
            duration_minutes=20.0,
        )
        tracker = _make_tracker([this_week, last_week])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        result = week_minutes_for(hass, "person.alice")

        # Only this_week should be counted (30 min); last_week is outside this week
        assert result == 30.0

    def test_goal_progress_for_caps_at_100(self) -> None:
        """goal_progress_for returns at most 100 even when minutes exceed goal."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            goal_progress_for,
        )

        # 60 minutes done today, goal is only 30
        s = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=90,
            duration_minutes=60.0,
        )
        tracker = _make_tracker([s])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        result = goal_progress_for(hass, "person.alice", goal_minutes=30)

        assert result == 100

    def test_goal_progress_for_zero_goal(self) -> None:
        """goal_progress_for returns 0 when goal_minutes is 0 (avoid division by zero)."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            goal_progress_for,
        )

        hass = _make_hass_with_entries([])

        result = goal_progress_for(hass, "person.alice", goal_minutes=0)

        assert result == 0

    def test_iter_trackers_skips_missing_runtime_data(self) -> None:
        """_iter_trackers skips entries whose runtime_data is None."""
        from custom_components.beurer_daylight_lamps.therapy_hub import (
            today_minutes_for,
        )

        entry_no_runtime = MagicMock()
        entry_no_runtime.runtime_data = None  # simulate missing
        hass = MagicMock()
        hass.data = {}
        # Make getattr(entry, "runtime_data", None) return None
        entry_bad = MagicMock(spec=[])  # No attributes
        hass.config_entries.async_entries.return_value = [entry_bad]

        # Should not raise
        result = today_minutes_for(hass, "person.alice")
        assert result == 0.0


class TestBeurerPersonTherapySensor:
    """Unit tests for the BeurerPersonTherapySensor entity."""

    def test_person_therapy_sensor_native_value_today(self) -> None:
        """BeurerPersonTherapySensor with kind='today' returns today_minutes_for result."""
        from custom_components.beurer_daylight_lamps.sensor import (
            BeurerPersonTherapySensor,
        )

        session = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=60,
            duration_minutes=25.0,
        )
        tracker = _make_tracker([session])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        sensor = BeurerPersonTherapySensor(hass, "person.alice", "alice", "today")

        assert sensor.native_value == 25.0

    def test_person_therapy_sensor_native_value_week(self) -> None:
        """BeurerPersonTherapySensor with kind='week' returns week_minutes_for result."""
        from custom_components.beurer_daylight_lamps.sensor import (
            BeurerPersonTherapySensor,
        )

        session = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=2 * 24 * 60,
            duration_minutes=40.0,
        )
        tracker = _make_tracker([session])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])

        sensor = BeurerPersonTherapySensor(hass, "person.alice", "alice", "week")

        assert sensor.native_value == 40.0

    def test_person_therapy_sensor_native_value_progress(self) -> None:
        """BeurerPersonTherapySensor with kind='progress' returns goal_progress_for result."""
        from custom_components.beurer_daylight_lamps.sensor import (
            BeurerPersonTherapySensor,
        )

        # 15 minutes today, goal=30 → 50%
        session = _make_session(
            "person.alice",
            is_therapy=True,
            start_offset_minutes=60,
            duration_minutes=15.0,
        )
        tracker = _make_tracker([session])
        entry = _make_entry_with_tracker(tracker)
        hass = _make_hass_with_entries([entry])
        # Provide options with therapy_goal=30 on the entry
        entry.options = {"therapy_goal": 30}

        sensor = BeurerPersonTherapySensor(hass, "person.alice", "alice", "progress")

        assert sensor.native_value == 50

    def test_person_therapy_sensor_device_info_uses_hub_identifier(self) -> None:
        """BeurerPersonTherapySensor device_info references the hub identifier."""
        from custom_components.beurer_daylight_lamps.const import (
            DOMAIN,
            THERAPY_HUB_IDENTIFIER,
        )
        from custom_components.beurer_daylight_lamps.sensor import (
            BeurerPersonTherapySensor,
        )

        hass = _make_hass_with_entries([])
        sensor = BeurerPersonTherapySensor(hass, "person.alice", "alice", "today")
        info = sensor.device_info

        assert (DOMAIN, THERAPY_HUB_IDENTIFIER) in info["identifiers"]

    def test_person_therapy_sensor_unique_ids_are_distinct(self) -> None:
        """Three kinds produce three distinct unique IDs for the same person."""
        from custom_components.beurer_daylight_lamps.sensor import (
            BeurerPersonTherapySensor,
        )

        hass = _make_hass_with_entries([])
        s_today = BeurerPersonTherapySensor(hass, "person.alice", "alice", "today")
        s_week = BeurerPersonTherapySensor(hass, "person.alice", "alice", "week")
        s_prog = BeurerPersonTherapySensor(hass, "person.alice", "alice", "progress")

        ids = {s_today.unique_id, s_week.unique_id, s_prog.unique_id}
        assert len(ids) == 3

    def test_person_therapy_sensor_units(self) -> None:
        """today and week sensors use minutes; progress uses percent."""
        from custom_components.beurer_daylight_lamps.sensor import (
            BeurerPersonTherapySensor,
        )

        hass = _make_hass_with_entries([])
        s_today = BeurerPersonTherapySensor(hass, "person.alice", "alice", "today")
        s_week = BeurerPersonTherapySensor(hass, "person.alice", "alice", "week")
        s_prog = BeurerPersonTherapySensor(hass, "person.alice", "alice", "progress")

        assert s_today.native_unit_of_measurement == "min"
        assert s_week.native_unit_of_measurement == "min"
        assert s_prog.native_unit_of_measurement == "%"


# ---------------------------------------------------------------------------
# Dynamic person listener tests
# ---------------------------------------------------------------------------


class TestDynamicPersonListener:
    """Unit tests for _handle_new_person: dynamically adds sensors at runtime."""

    def test_handle_new_person_adds_three_sensors(self) -> None:
        """_handle_new_person adds today/week/progress sensors for a newly seen person."""
        from unittest.mock import MagicMock

        from custom_components.beurer_daylight_lamps.sensor import _make_person_listener

        hass = _make_hass_with_entries([])
        hass.states = MagicMock()
        hass.states.async_all.return_value = []  # No persons at setup time

        async_add_entities = MagicMock()
        known_persons: set[str] = set()

        handler = _make_person_listener(hass, async_add_entities, known_persons)

        # Fire a fake state_added event for person.anna
        fake_event = MagicMock()
        fake_event.data = {"entity_id": "person.anna"}
        handler(fake_event)

        async_add_entities.assert_called_once()
        added = async_add_entities.call_args[0][0]
        assert len(added) == 3
        kinds = {e._kind for e in added}
        assert kinds == {"today", "week", "progress"}
        for entity in added:
            assert entity._person == "person.anna"

    def test_handle_new_person_deduplicates_same_person(self) -> None:
        """_handle_new_person does NOT add sensors again if person already known."""
        from unittest.mock import MagicMock

        from custom_components.beurer_daylight_lamps.sensor import _make_person_listener

        hass = _make_hass_with_entries([])
        async_add_entities = MagicMock()
        known_persons: set[str] = {"person.anna"}  # pre-populated

        handler = _make_person_listener(hass, async_add_entities, known_persons)

        fake_event = MagicMock()
        fake_event.data = {"entity_id": "person.anna"}
        handler(fake_event)

        async_add_entities.assert_not_called()

    def test_handle_new_person_updates_known_set(self) -> None:
        """After _handle_new_person fires, the person is added to known_persons."""
        from unittest.mock import MagicMock

        from custom_components.beurer_daylight_lamps.sensor import _make_person_listener

        hass = _make_hass_with_entries([])
        async_add_entities = MagicMock()
        known_persons: set[str] = set()

        handler = _make_person_listener(hass, async_add_entities, known_persons)

        fake_event = MagicMock()
        fake_event.data = {"entity_id": "person.bob"}
        handler(fake_event)

        assert "person.bob" in known_persons

    def test_handle_new_person_called_twice_adds_once(self) -> None:
        """Firing state_added twice for same person only creates sensors once."""
        from unittest.mock import MagicMock

        from custom_components.beurer_daylight_lamps.sensor import _make_person_listener

        hass = _make_hass_with_entries([])
        async_add_entities = MagicMock()
        known_persons: set[str] = set()

        handler = _make_person_listener(hass, async_add_entities, known_persons)

        fake_event = MagicMock()
        fake_event.data = {"entity_id": "person.carol"}
        handler(fake_event)
        handler(fake_event)  # fire again — should be a no-op

        assert async_add_entities.call_count == 1


# ---------------------------------------------------------------------------
# C1: Implicit session-end fires event
# ---------------------------------------------------------------------------


class TestImplicitSessionEnd:
    """Verify that start_session returns the displaced session and callers fire the event."""

    def test_start_session_returns_ended_session(self) -> None:
        """TherapyTracker.start_session returns the previously active session when one is displaced."""
        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        tracker = TherapyTracker()
        # Start session for person A
        tracker.start_session(5300, 100, person_id="person.alice")
        # Backdate to ensure session qualifies (>= 1 min, therapy light)
        from datetime import UTC, datetime, timedelta

        tracker._current_session.start_time = datetime.now(UTC) - timedelta(minutes=5)

        # Starting session for person B should return A's ended session
        returned = tracker.start_session(5300, 100, person_id="person.bob")

        assert returned is not None
        assert returned.person_id == "person.alice"
        assert returned.end_time is not None  # was ended
        assert tracker._current_session.person_id == "person.bob"

    def test_start_session_returns_none_when_no_prior_session(self) -> None:
        """TherapyTracker.start_session returns None when no prior session was active."""
        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        tracker = TherapyTracker()
        returned = tracker.start_session(5300, 100, person_id="person.alice")

        assert returned is None

    def test_implicit_end_fires_event_at_instance_level(self) -> None:
        """When start_session displaces an old session, an event is fired for the old session."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_implicit"
        instance._entry = mock_entry
        instance._device_name = "Implicit Lamp"

        from datetime import UTC, datetime, timedelta

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()

        # Directly start session for person A (bypassing _track_therapy_from_rgb)
        instance._therapy_tracker.start_session(5300, 100, person_id="person.alice")
        instance._therapy_tracker._current_session.start_time = datetime.now(
            UTC
        ) - timedelta(minutes=5)

        # Now simulate a second start_session (person B) via _emit_session_end path
        ended = instance._therapy_tracker.start_session(
            5300, 100, person_id="person.bob"
        )
        instance._emit_session_end(ended)

        # Event for person A should have fired once
        mock_hass.bus.async_fire.assert_called_once()
        event_name, payload = mock_hass.bus.async_fire.call_args[0]
        assert event_name == EVENT_THERAPY_SESSION
        assert payload["person_id"] == "person.alice"

    def test_implicit_end_no_event_when_no_prior_session(self) -> None:
        """_emit_session_end(None) does not fire any event."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        instance._entry = MagicMock()
        instance._device_name = "Empty"

        instance._emit_session_end(None)

        mock_hass.bus.async_fire.assert_not_called()


# ---------------------------------------------------------------------------
# I4: light_entity_id present in event payload
# ---------------------------------------------------------------------------


class TestLightEntityIdInPayload:
    """Verify that EVENT_THERAPY_SESSION payload includes light_entity_id."""

    def test_event_payload_includes_light_entity_id(self) -> None:
        """light_entity_id from the entity registry is included in the event payload."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_light"
        instance._entry = mock_entry
        instance._device_name = "Light Lamp"

        from datetime import UTC, datetime, timedelta

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 100, person_id="person.alice")
        instance._therapy_tracker._current_session.start_time = datetime.now(
            UTC
        ) - timedelta(minutes=5)

        # Mock the entity registry to return a known entity_id
        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.return_value = "light.beurer_tl100"

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.er.async_get",
            return_value=mock_registry,
        ):
            instance._end_therapy_and_emit()

        mock_hass.bus.async_fire.assert_called_once()
        _, payload = mock_hass.bus.async_fire.call_args[0]
        assert "light_entity_id" in payload
        assert payload["light_entity_id"] == "light.beurer_tl100"

    def test_event_payload_light_entity_id_none_when_not_found(self) -> None:
        """light_entity_id is None when the entity registry lookup returns nothing."""
        mock_hass = _make_mock_hass()
        instance = _make_beurer_instance(hass=mock_hass)
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_no_light"
        instance._entry = mock_entry
        instance._device_name = "No Light"

        from datetime import UTC, datetime, timedelta

        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance._therapy_tracker = TherapyTracker()
        instance._therapy_tracker.start_session(5300, 100, person_id=None)
        instance._therapy_tracker._current_session.start_time = datetime.now(
            UTC
        ) - timedelta(minutes=5)

        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.return_value = None

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.er.async_get",
            return_value=mock_registry,
        ):
            instance._end_therapy_and_emit()

        _, payload = mock_hass.bus.async_fire.call_args[0]
        assert payload["light_entity_id"] is None
