"""Light therapy management for Beurer Daylight Lamps.

This module provides:
1. Sunrise/Sunset simulation via native services (no YAML required)
2. Daily light exposure tracking for therapy goals
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from enum import Enum

from homeassistant.util.color import color_temperature_to_rgb

if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance

from .const import LOGGER


class SunriseProfile(Enum):
    """Predefined sunrise profiles."""

    GENTLE = "gentle"      # Very slow, warm start
    NATURAL = "natural"    # Natural sunrise simulation
    ENERGIZE = "energize"  # Fast, cool light for alertness
    THERAPY = "therapy"    # Optimized for light therapy (ends at 5300K)


@dataclass
class SunriseConfig:
    """Configuration for sunrise profile."""

    start_kelvin: int
    end_kelvin: int
    start_brightness_pct: int
    end_brightness_pct: int
    description: str


# Profile configurations
SUNRISE_PROFILES: dict[SunriseProfile, SunriseConfig] = {
    SunriseProfile.GENTLE: SunriseConfig(
        start_kelvin=2200,
        end_kelvin=3500,
        start_brightness_pct=5,
        end_brightness_pct=60,
        description="Very gentle wake-up with warm light",
    ),
    SunriseProfile.NATURAL: SunriseConfig(
        start_kelvin=2700,
        end_kelvin=5000,
        start_brightness_pct=10,
        end_brightness_pct=100,
        description="Natural sunrise simulation",
    ),
    SunriseProfile.ENERGIZE: SunriseConfig(
        start_kelvin=3500,
        end_kelvin=6500,
        start_brightness_pct=20,
        end_brightness_pct=100,
        description="Fast energizing wake-up",
    ),
    SunriseProfile.THERAPY: SunriseConfig(
        start_kelvin=2700,
        end_kelvin=5300,
        start_brightness_pct=10,
        end_brightness_pct=100,
        description="Optimized for light therapy",
    ),
}


@dataclass
class TherapySession:
    """Tracks a single therapy session."""

    start_time: datetime
    end_time: datetime | None = None
    color_temp_kelvin: int = 5300
    brightness_pct: int = 100

    @property
    def duration_minutes(self) -> float:
        """Calculate session duration in minutes."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds() / 60

    @property
    def is_therapy_light(self) -> bool:
        """Check if this qualifies as therapy light (bright + cool)."""
        return self.color_temp_kelvin >= 5000 and self.brightness_pct >= 80


@dataclass
class TherapyTracker:
    """Tracks daily light therapy exposure."""

    sessions: list[TherapySession] = field(default_factory=list)
    daily_goal_minutes: int = 30
    _current_session: TherapySession | None = None

    def start_session(
        self,
        color_temp_kelvin: int = 5300,
        brightness_pct: int = 100,
    ) -> None:
        """Start tracking a new therapy session."""
        if self._current_session is not None:
            self.end_session()

        self._current_session = TherapySession(
            start_time=datetime.now(),
            color_temp_kelvin=color_temp_kelvin,
            brightness_pct=brightness_pct,
        )
        LOGGER.debug(
            "Started therapy session: %dK @ %d%%",
            color_temp_kelvin,
            brightness_pct,
        )

    def update_session(
        self,
        color_temp_kelvin: int | None = None,
        brightness_pct: int | None = None,
    ) -> None:
        """Update current session parameters."""
        if self._current_session is None:
            return

        if color_temp_kelvin is not None:
            self._current_session.color_temp_kelvin = color_temp_kelvin
        if brightness_pct is not None:
            self._current_session.brightness_pct = brightness_pct

    def end_session(self) -> TherapySession | None:
        """End current session and add to history."""
        if self._current_session is None:
            return None

        self._current_session.end_time = datetime.now()
        session = self._current_session

        # Only track sessions that qualify as therapy
        if session.is_therapy_light and session.duration_minutes >= 1:
            self.sessions.append(session)
            LOGGER.debug(
                "Ended therapy session: %.1f minutes",
                session.duration_minutes,
            )

        self._current_session = None
        return session

    def cleanup_old_sessions(self) -> None:
        """Remove sessions older than 7 days."""
        cutoff = datetime.now() - timedelta(days=7)
        self.sessions = [s for s in self.sessions if s.start_time > cutoff]

    @property
    def today_minutes(self) -> float:
        """Calculate total therapy minutes today."""
        today = datetime.now().date()
        total = 0.0

        for session in self.sessions:
            if session.start_time.date() == today and session.is_therapy_light:
                total += session.duration_minutes

        # Add current session if active and qualifies
        if (
            self._current_session
            and self._current_session.start_time.date() == today
            and self._current_session.is_therapy_light
        ):
            total += self._current_session.duration_minutes

        return total

    @property
    def week_minutes(self) -> float:
        """Calculate total therapy minutes this week."""
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        total = 0.0
        for session in self.sessions:
            if session.start_time >= week_start and session.is_therapy_light:
                total += session.duration_minutes

        # Add current session
        if (
            self._current_session
            and self._current_session.start_time >= week_start
            and self._current_session.is_therapy_light
        ):
            total += self._current_session.duration_minutes

        return total

    @property
    def goal_reached(self) -> bool:
        """Check if daily goal is reached."""
        return self.today_minutes >= self.daily_goal_minutes

    @property
    def goal_progress_pct(self) -> int:
        """Calculate progress towards daily goal as percentage."""
        return min(100, int(self.today_minutes / self.daily_goal_minutes * 100))


class SunriseSimulation:
    """Manages sunrise/sunset light simulations."""

    def __init__(self, instance: BeurerInstance) -> None:
        """Initialize sunrise simulation."""
        self._instance = instance
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._current_step = 0
        self._total_steps = 0

    @property
    def is_running(self) -> bool:
        """Return True if simulation is currently running."""
        return self._running

    @property
    def progress_pct(self) -> int:
        """Return current progress as percentage."""
        if not self._running or self._total_steps == 0:
            return 0
        return int(self._current_step / self._total_steps * 100)

    async def start_sunrise(
        self,
        duration_minutes: int = 15,
        profile: SunriseProfile = SunriseProfile.NATURAL,
    ) -> None:
        """Start a sunrise simulation.

        Args:
            duration_minutes: Total duration of the sunrise
            profile: The sunrise profile to use
        """
        if self._running:
            await self.stop()

        config = SUNRISE_PROFILES[profile]
        LOGGER.info(
            "Starting sunrise: %d min, profile=%s (%s)",
            duration_minutes,
            profile.value,
            config.description,
        )

        self._running = True
        self._task = asyncio.create_task(
            self._run_sunrise(duration_minutes, config)
        )

    async def start_sunset(
        self,
        duration_minutes: int = 30,
        end_brightness_pct: int = 0,
    ) -> None:
        """Start a sunset simulation (gradual dimming).

        Args:
            duration_minutes: Total duration of the sunset
            end_brightness_pct: Final brightness (0 = turn off)
        """
        if self._running:
            await self.stop()

        LOGGER.info(
            "Starting sunset: %d min, end_brightness=%d%%",
            duration_minutes,
            end_brightness_pct,
        )

        self._running = True
        self._task = asyncio.create_task(
            self._run_sunset(duration_minutes, end_brightness_pct)
        )

    async def stop(self) -> None:
        """Stop any running simulation."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._current_step = 0
        self._total_steps = 0
        LOGGER.debug("Simulation stopped")

    async def _apply_with_retry(
        self,
        action: Any,
        max_retries: int = 3,
    ) -> bool:
        """Apply an action with retry and automatic reconnection.

        Args:
            action: Async callable to execute
            max_retries: Maximum number of retry attempts

        Returns:
            True if action succeeded, False otherwise
        """
        for attempt in range(max_retries):
            try:
                # Check connection status and reconnect if needed
                if not self._instance.is_connected:
                    LOGGER.debug("Not connected, attempting reconnect...")
                    connected = await self._instance.connect()
                    if not connected:
                        LOGGER.warning(
                            "Reconnect failed (attempt %d/%d)",
                            attempt + 1, max_retries
                        )
                        await asyncio.sleep(1)
                        continue

                # Execute the action
                await action()
                return True

            except Exception as err:
                LOGGER.warning(
                    "Action failed (attempt %d/%d): %s",
                    attempt + 1, max_retries, err
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        return False

    async def _run_sunrise(
        self,
        duration_minutes: int,
        config: SunriseConfig,
    ) -> None:
        """Execute sunrise simulation.

        Resilient to connection issues - will retry and continue on errors.
        """
        try:
            # Calculate steps (one per minute, minimum 1)
            steps = max(1, duration_minutes)
            self._total_steps = steps
            interval = duration_minutes * 60 / steps  # seconds between steps

            kelvin_step = (config.end_kelvin - config.start_kelvin) / steps
            brightness_step = (config.end_brightness_pct - config.start_brightness_pct) / steps

            consecutive_failures = 0
            max_consecutive_failures = 5

            for i in range(steps + 1):
                if not self._running:
                    break

                self._current_step = i

                # Calculate current values
                kelvin = int(config.start_kelvin + kelvin_step * i)
                brightness_pct = int(config.start_brightness_pct + brightness_step * i)
                brightness_255 = int(brightness_pct / 100 * 255)

                # Convert kelvin to RGB (convert floats to ints)
                rgb_float = color_temperature_to_rgb(kelvin)
                rgb: tuple[int, int, int] = (
                    int(rgb_float[0]),
                    int(rgb_float[1]),
                    int(rgb_float[2]),
                )

                LOGGER.debug(
                    "Sunrise step %d/%d: %dK @ %d%%",
                    i + 1,
                    steps + 1,
                    kelvin,
                    brightness_pct,
                )

                # Apply to lamp with retry logic
                # Capture values for lambda to avoid late binding issues
                _rgb, _brightness = rgb, brightness_255
                success = await self._apply_with_retry(
                    lambda: self._instance.set_color_with_brightness(_rgb, _brightness)
                )

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    LOGGER.warning(
                        "Sunrise step %d failed, continuing... (%d consecutive failures)",
                        i + 1, consecutive_failures
                    )
                    if consecutive_failures >= max_consecutive_failures:
                        LOGGER.error(
                            "Too many consecutive failures (%d), stopping sunrise",
                            consecutive_failures
                        )
                        break

                if i < steps:
                    await asyncio.sleep(interval)

            LOGGER.info("Sunrise simulation completed")

        except asyncio.CancelledError:
            LOGGER.debug("Sunrise simulation cancelled")
            raise
        finally:
            self._running = False
            self._current_step = 0
            self._total_steps = 0

    async def _run_sunset(
        self,
        duration_minutes: int,
        end_brightness_pct: int,
    ) -> None:
        """Execute sunset simulation.

        Resilient to connection issues - will retry and continue on errors.
        """
        try:
            # Get current brightness
            current_brightness = self._instance.color_brightness
            if current_brightness is None:
                current_brightness = self._instance.white_brightness or 255

            start_brightness_pct = int(current_brightness / 255 * 100)

            # Calculate steps (one per minute)
            steps = max(1, duration_minutes)
            self._total_steps = steps
            interval = duration_minutes * 60 / steps

            brightness_step = (start_brightness_pct - end_brightness_pct) / steps

            # Use warm light for sunset (convert floats to ints)
            warm_rgb_float = color_temperature_to_rgb(2700)
            warm_rgb: tuple[int, int, int] = (
                int(warm_rgb_float[0]),
                int(warm_rgb_float[1]),
                int(warm_rgb_float[2]),
            )

            consecutive_failures = 0
            max_consecutive_failures = 5

            for i in range(steps + 1):
                if not self._running:
                    break

                self._current_step = i
                brightness_pct = int(start_brightness_pct - brightness_step * i)
                brightness_255 = int(brightness_pct / 100 * 255)

                LOGGER.debug(
                    "Sunset step %d/%d: %d%%",
                    i + 1,
                    steps + 1,
                    brightness_pct,
                )

                # Apply with retry logic
                if brightness_pct <= 0:
                    success = await self._apply_with_retry(
                        lambda: self._instance.turn_off()
                    )
                else:
                    # Capture values for lambda
                    _rgb, _brightness = warm_rgb, brightness_255
                    success = await self._apply_with_retry(
                        lambda: self._instance.set_color_with_brightness(_rgb, _brightness)
                    )

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    LOGGER.warning(
                        "Sunset step %d failed, continuing... (%d consecutive failures)",
                        i + 1, consecutive_failures
                    )
                    if consecutive_failures >= max_consecutive_failures:
                        LOGGER.error(
                            "Too many consecutive failures (%d), stopping sunset",
                            consecutive_failures
                        )
                        break

                if i < steps:
                    await asyncio.sleep(interval)

            # Final turn off if end_brightness is 0
            if end_brightness_pct == 0 and self._running:
                await self._apply_with_retry(lambda: self._instance.turn_off())

            LOGGER.info("Sunset simulation completed")

        except asyncio.CancelledError:
            LOGGER.debug("Sunset simulation cancelled")
            raise
        finally:
            self._running = False
            self._current_step = 0
            self._total_steps = 0
