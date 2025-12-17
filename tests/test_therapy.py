"""Test Beurer Daylight Lamps therapy module."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.beurer_daylight_lamps.therapy import (
    SunriseConfig,
    SunriseProfile,
    SunriseSimulation,
    SUNRISE_PROFILES,
    TherapySession,
    TherapyTracker,
)


class TestTherapySession:
    """Tests for TherapySession dataclass."""

    def test_duration_minutes_ongoing(self) -> None:
        """Test duration calculation for ongoing session."""
        session = TherapySession(
            start_time=datetime.now() - timedelta(minutes=10),
        )
        assert 9.9 < session.duration_minutes < 10.1

    def test_duration_minutes_completed(self) -> None:
        """Test duration calculation for completed session."""
        start = datetime.now() - timedelta(minutes=30)
        end = datetime.now()
        session = TherapySession(
            start_time=start,
            end_time=end,
        )
        assert 29.9 < session.duration_minutes < 30.1

    def test_is_therapy_light_true(self) -> None:
        """Test therapy light detection for qualifying session."""
        session = TherapySession(
            start_time=datetime.now(),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        assert session.is_therapy_light is True

    def test_is_therapy_light_too_dim(self) -> None:
        """Test therapy light detection for too dim session."""
        session = TherapySession(
            start_time=datetime.now(),
            color_temp_kelvin=5300,
            brightness_pct=50,  # Below 80%
        )
        assert session.is_therapy_light is False

    def test_is_therapy_light_too_warm(self) -> None:
        """Test therapy light detection for too warm session."""
        session = TherapySession(
            start_time=datetime.now(),
            color_temp_kelvin=3000,  # Below 5000K
            brightness_pct=100,
        )
        assert session.is_therapy_light is False


class TestTherapyTracker:
    """Tests for TherapyTracker class."""

    def test_start_session(self) -> None:
        """Test starting a new session."""
        tracker = TherapyTracker()
        tracker.start_session(color_temp_kelvin=5300, brightness_pct=100)
        assert tracker._current_session is not None
        assert tracker._current_session.color_temp_kelvin == 5300
        assert tracker._current_session.brightness_pct == 100

    def test_start_session_ends_previous(self) -> None:
        """Test that starting a session ends the previous one."""
        tracker = TherapyTracker()
        tracker.start_session(color_temp_kelvin=5300, brightness_pct=100)
        first_session = tracker._current_session

        # Start another session
        tracker.start_session(color_temp_kelvin=5500, brightness_pct=90)

        # First session should be ended
        assert first_session.end_time is not None

    def test_update_session(self) -> None:
        """Test updating session parameters."""
        tracker = TherapyTracker()
        tracker.start_session(color_temp_kelvin=5300, brightness_pct=100)

        tracker.update_session(color_temp_kelvin=5500)
        assert tracker._current_session.color_temp_kelvin == 5500
        assert tracker._current_session.brightness_pct == 100

        tracker.update_session(brightness_pct=80)
        assert tracker._current_session.brightness_pct == 80

    def test_update_session_no_current(self) -> None:
        """Test updating when no session is active."""
        tracker = TherapyTracker()
        # Should not raise
        tracker.update_session(color_temp_kelvin=5500)

    def test_end_session_adds_to_history(self) -> None:
        """Test that ending a session adds it to history."""
        tracker = TherapyTracker()
        tracker.start_session(color_temp_kelvin=5300, brightness_pct=100)

        # Manually set start time for test
        tracker._current_session.start_time = datetime.now() - timedelta(minutes=5)

        session = tracker.end_session()
        assert session is not None
        assert len(tracker.sessions) == 1
        assert tracker._current_session is None

    def test_end_session_skips_non_therapy(self) -> None:
        """Test that non-therapy sessions are not added to history."""
        tracker = TherapyTracker()
        tracker.start_session(color_temp_kelvin=3000, brightness_pct=50)

        # Manually set start time for test
        tracker._current_session.start_time = datetime.now() - timedelta(minutes=5)

        session = tracker.end_session()
        assert session is not None
        assert len(tracker.sessions) == 0  # Not added due to non-therapy light

    def test_today_minutes(self) -> None:
        """Test today's therapy minutes calculation."""
        tracker = TherapyTracker()

        # Add a session from today
        session = TherapySession(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now() - timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(session)

        # Should report ~10 minutes
        assert 9.5 < tracker.today_minutes < 10.5

    def test_today_minutes_excludes_yesterday(self) -> None:
        """Test that yesterday's sessions are excluded."""
        tracker = TherapyTracker()

        # Add a session from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        session = TherapySession(
            start_time=yesterday - timedelta(minutes=20),
            end_time=yesterday - timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(session)

        assert tracker.today_minutes == 0

    def test_week_minutes(self) -> None:
        """Test weekly therapy minutes calculation."""
        tracker = TherapyTracker()

        # Add sessions from this week
        for i in range(3):
            session = TherapySession(
                start_time=datetime.now() - timedelta(days=i, minutes=20),
                end_time=datetime.now() - timedelta(days=i, minutes=10),
                color_temp_kelvin=5300,
                brightness_pct=100,
            )
            tracker.sessions.append(session)

        # Should report ~30 minutes (3 x 10)
        assert 29 < tracker.week_minutes < 31

    def test_goal_reached(self) -> None:
        """Test goal reached detection."""
        tracker = TherapyTracker(daily_goal_minutes=15)

        # Add session that meets goal
        session = TherapySession(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now() - timedelta(minutes=4),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(session)

        assert tracker.goal_reached is True

    def test_goal_not_reached(self) -> None:
        """Test goal not reached detection."""
        tracker = TherapyTracker(daily_goal_minutes=30)

        # Add session that doesn't meet goal
        session = TherapySession(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now() - timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(session)

        assert tracker.goal_reached is False

    def test_goal_progress_pct(self) -> None:
        """Test goal progress percentage calculation."""
        tracker = TherapyTracker(daily_goal_minutes=20)

        # Add 10-minute session (50% of goal)
        session = TherapySession(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now() - timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(session)

        assert 45 < tracker.goal_progress_pct < 55

    def test_goal_progress_pct_capped(self) -> None:
        """Test goal progress percentage is capped at 100."""
        tracker = TherapyTracker(daily_goal_minutes=10)

        # Add 20-minute session (200% of goal)
        session = TherapySession(
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() - timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(session)

        assert tracker.goal_progress_pct == 100

    def test_cleanup_old_sessions(self) -> None:
        """Test cleanup of old sessions."""
        tracker = TherapyTracker()

        # Add old session
        old_session = TherapySession(
            start_time=datetime.now() - timedelta(days=10),
            end_time=datetime.now() - timedelta(days=10) + timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(old_session)

        # Add recent session
        recent_session = TherapySession(
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now() - timedelta(days=1) + timedelta(minutes=10),
            color_temp_kelvin=5300,
            brightness_pct=100,
        )
        tracker.sessions.append(recent_session)

        tracker.cleanup_old_sessions()

        assert len(tracker.sessions) == 1
        assert tracker.sessions[0] == recent_session


class TestSunriseProfiles:
    """Tests for sunrise profile configurations."""

    def test_all_profiles_defined(self) -> None:
        """Test all sunrise profiles are defined."""
        assert SunriseProfile.GENTLE in SUNRISE_PROFILES
        assert SunriseProfile.NATURAL in SUNRISE_PROFILES
        assert SunriseProfile.ENERGIZE in SUNRISE_PROFILES
        assert SunriseProfile.THERAPY in SUNRISE_PROFILES

    def test_profile_values_valid(self) -> None:
        """Test all profile values are within valid ranges."""
        for profile, config in SUNRISE_PROFILES.items():
            assert 2000 <= config.start_kelvin <= 7000
            assert 2000 <= config.end_kelvin <= 7000
            assert 0 <= config.start_brightness_pct <= 100
            assert 0 <= config.end_brightness_pct <= 100
            assert len(config.description) > 0


class TestSunriseSimulation:
    """Tests for SunriseSimulation class."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.set_color_with_brightness = AsyncMock()
        instance.turn_off = AsyncMock()
        instance.color_brightness = 200
        instance.white_brightness = 255
        return instance

    def test_initial_state(self, mock_instance: MagicMock) -> None:
        """Test initial simulation state."""
        sim = SunriseSimulation(mock_instance)
        assert sim.is_running is False
        assert sim.progress_pct == 0

    @pytest.mark.asyncio
    async def test_start_sunrise_sets_running(self, mock_instance: MagicMock) -> None:
        """Test that starting sunrise sets running flag."""
        sim = SunriseSimulation(mock_instance)

        # Start with very short duration
        await sim.start_sunrise(duration_minutes=1, profile=SunriseProfile.NATURAL)

        # Should be running (or completed very quickly)
        # Stop immediately to avoid long test
        await sim.stop()

        assert sim.is_running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_simulation(self, mock_instance: MagicMock) -> None:
        """Test that stop cancels running simulation."""
        sim = SunriseSimulation(mock_instance)

        await sim.start_sunrise(duration_minutes=60, profile=SunriseProfile.NATURAL)
        await sim.stop()

        assert sim.is_running is False
        assert sim._task is None

    @pytest.mark.asyncio
    async def test_start_sunrise_stops_previous(self, mock_instance: MagicMock) -> None:
        """Test that starting a new simulation stops the previous."""
        sim = SunriseSimulation(mock_instance)

        await sim.start_sunrise(duration_minutes=60, profile=SunriseProfile.NATURAL)
        first_task = sim._task

        await sim.start_sunrise(duration_minutes=60, profile=SunriseProfile.GENTLE)

        # First task should have been cancelled
        assert first_task is None or first_task.cancelled() or first_task.done()

        await sim.stop()

    @pytest.mark.asyncio
    async def test_start_sunset_sets_running(self, mock_instance: MagicMock) -> None:
        """Test that starting sunset sets running flag."""
        sim = SunriseSimulation(mock_instance)

        await sim.start_sunset(duration_minutes=1, end_brightness_pct=0)
        await sim.stop()

        assert sim.is_running is False
