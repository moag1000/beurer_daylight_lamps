"""Tests for persisting therapy history across restarts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from custom_components.beurer_daylight_lamps import (
    _async_options_updated,
    _async_setup_therapy_storage,
    _therapy_store,
    async_remove_entry,
)
from custom_components.beurer_daylight_lamps.const import DOMAIN
from custom_components.beurer_daylight_lamps.therapy import (
    TherapySession,
    TherapyTracker,
)


def _session(minutes_ago: float, length: float) -> TherapySession:
    start = datetime.now(tz=UTC) - timedelta(minutes=minutes_ago)
    return TherapySession(start_time=start, end_time=start + timedelta(minutes=length))


def test_round_trip_keeps_sessions_and_goal() -> None:
    """Stored sessions and goal come back unchanged."""
    tracker = TherapyTracker(daily_goal_minutes=45)
    tracker.sessions = [_session(60, 20), _session(30, 10)]

    restored = TherapyTracker()
    restored.load_storage_dict(tracker.as_storage_dict())

    assert restored.daily_goal_minutes == 45
    assert len(restored.sessions) == 2
    assert round(restored.week_minutes) == round(tracker.week_minutes)


def test_running_session_is_stored_up_to_now() -> None:
    """A restart during a session keeps the minutes so far."""
    tracker = TherapyTracker()
    tracker.start_session(5300, 100)
    tracker._current_session.start_time -= timedelta(minutes=12)

    data = tracker.as_storage_dict()

    assert len(data["sessions"]) == 1
    assert tracker.has_active_session  # storing does not end the session
    restored = TherapyTracker()
    restored.load_storage_dict(data)
    assert 11.9 < restored.sessions[0].duration_minutes < 12.5


def test_old_and_invalid_entries_are_dropped() -> None:
    """Sessions older than 7 days and broken entries are skipped."""
    tracker = TherapyTracker()
    tracker.load_storage_dict(
        {
            "daily_goal_minutes": 500,  # out of range: keep default
            "sessions": [
                {"start": "not a date", "end": "x"},
                {"end": datetime.now(tz=UTC).isoformat()},
                {
                    "start": (datetime.now(tz=UTC) - timedelta(days=9)).isoformat(),
                    "end": (datetime.now(tz=UTC) - timedelta(days=9)).isoformat(),
                },
                {
                    "start": (datetime.now(tz=UTC) - timedelta(minutes=5)).isoformat(),
                    "end": datetime.now(tz=UTC).isoformat(),
                },
            ],
        }
    )
    assert tracker.daily_goal_minutes == 30
    assert len(tracker.sessions) == 1


def test_changes_notify_owner() -> None:
    """Finished sessions and goal changes ask for a save."""
    tracker = TherapyTracker()
    tracker.on_change = MagicMock()

    tracker.start_session(5300, 100)
    tracker._current_session.start_time -= timedelta(minutes=5)
    tracker.end_session()
    tracker.notify_changed()

    assert tracker.on_change.call_count == 2


async def test_setup_restores_and_saves(hass, hass_storage) -> None:
    """Setup restores the stored history and schedules saves on change."""
    entry_id = "entry1"
    stored = TherapyTracker(daily_goal_minutes=50)
    stored.sessions = [_session(30, 15)]
    hass_storage[f"{DOMAIN}.therapy.{entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.therapy.{entry_id}",
        "data": stored.as_storage_dict(),
    }
    instance = MagicMock()
    instance.therapy_tracker = TherapyTracker()
    entry = MagicMock(entry_id=entry_id, title="Bedroom")

    store = await _async_setup_therapy_storage(hass, entry, instance)

    tracker = instance.therapy_tracker
    assert tracker.daily_goal_minutes == 50
    assert len(tracker.sessions) == 1

    tracker.daily_goal_minutes = 20
    tracker.notify_changed()
    await store._async_handle_write_data()
    assert hass_storage[store.key]["data"]["daily_goal_minutes"] == 20

    await async_remove_entry(hass, entry)
    assert _therapy_store(hass, entry_id).key not in hass_storage


async def test_options_goal_used_on_first_start(hass) -> None:
    """Without stored data the goal from the options is used."""
    instance = MagicMock()
    instance.therapy_tracker = TherapyTracker()
    entry = MagicMock(entry_id="fresh", title="Desk", options={"therapy_goal": 45})

    await _async_setup_therapy_storage(hass, entry, instance)

    assert instance.therapy_tracker.daily_goal_minutes == 45


async def test_options_update_applies_goal(hass) -> None:
    """Changing the goal in the options updates the lamp."""
    instance = MagicMock()
    instance.therapy_daily_goal = 30
    entry = MagicMock(
        options={"therapy_goal": 40},
        runtime_data=MagicMock(instance=instance),
    )

    await _async_options_updated(hass, entry)
    instance.set_therapy_daily_goal.assert_called_once_with(40)

    instance.set_therapy_daily_goal.reset_mock()
    instance.therapy_daily_goal = 40
    await _async_options_updated(hass, entry)
    instance.set_therapy_daily_goal.assert_not_called()


async def test_today_uses_local_day(hass, freezer) -> None:
    """A session at 00:30 local time counts for the new local day."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    # 2026-11-10 00:30 in Berlin is 2026-11-09 23:30 UTC
    freezer.move_to("2026-11-09 23:45:00+00:00")
    tracker = TherapyTracker()
    tracker.sessions = [
        TherapySession(
            start_time=datetime(2026, 11, 9, 23, 30, tzinfo=UTC),
            end_time=datetime(2026, 11, 9, 23, 40, tzinfo=UTC),
        ),
        # 22:00 UTC on the 9th is 23:00 in Berlin: yesterday
        TherapySession(
            start_time=datetime(2026, 11, 9, 22, 0, tzinfo=UTC),
            end_time=datetime(2026, 11, 9, 22, 20, tzinfo=UTC),
        ),
    ]
    assert round(tracker.today_minutes) == 10
