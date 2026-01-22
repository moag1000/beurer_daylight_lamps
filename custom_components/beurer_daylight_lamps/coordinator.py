"""DataUpdateCoordinator for Beurer Daylight Lamps.

This module implements the DataUpdateCoordinator pattern for centralized
data management and update coordination across all entities.

For BLE devices, we use a hybrid approach:
- Primary updates come from BLE notifications (push)
- Periodic refresh ensures state consistency
- Coordinator manages update distribution to all entities
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ColorMode  # type: ignore[attr-defined]
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    POLL_INTERVAL_LIGHT_ON,
    POLL_INTERVAL_LIGHT_OFF,
    POLL_INTERVAL_UNAVAILABLE,
)

if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance


# Default update interval (used initially before state is known)
# Will be dynamically adjusted based on device state
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=POLL_INTERVAL_LIGHT_OFF)


class BeurerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Beurer device data updates.

    This coordinator manages data from the BeurerInstance and distributes
    updates to all entities. It combines:
    - Push updates from BLE notifications
    - Periodic refresh for state verification
    - Centralized error handling
    """

    def __init__(
        self,
        hass: HomeAssistant,
        instance: BeurerInstance,
        name: str,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            instance: BeurerInstance for BLE communication
            name: Device name for logging
        """
        super().__init__(
            hass,
            LOGGER,
            name=f"Beurer {name}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
            always_update=False,  # Only update when data changes
        )
        self.instance = instance
        self.device_name = name

        # Track the current polling state for adaptive intervals
        self._last_poll_state: str = "unknown"

        # Register for push updates from BLE notifications
        self.instance.set_update_callback(self._handle_push_update)

    @callback
    def _handle_push_update(self) -> None:
        """Handle push update from BLE notification.

        This is called when the device sends a BLE notification.
        We update the coordinator data and notify all listeners.
        """
        LOGGER.debug("Push update received from %s", self.instance.mac)
        self.async_set_updated_data(self._get_current_data())
        # Adjust polling interval based on new state
        self._adjust_polling_interval()

    def _get_adaptive_interval(self) -> timedelta:
        """Calculate the appropriate polling interval based on device state.

        Returns:
            timedelta: The polling interval to use
        """
        # If device is unavailable, use longest interval
        if not self.instance.ble_available:
            return timedelta(seconds=POLL_INTERVAL_UNAVAILABLE)

        # If light is on, poll more frequently for responsive updates
        if self.instance.is_on:
            return timedelta(seconds=POLL_INTERVAL_LIGHT_ON)

        # Light is off but device is available - standard interval
        return timedelta(seconds=POLL_INTERVAL_LIGHT_OFF)

    def _get_poll_state(self) -> str:
        """Get a string representing current polling state."""
        if not self.instance.ble_available:
            return "unavailable"
        if self.instance.is_on:
            return "on"
        return "off"

    @callback
    def _adjust_polling_interval(self) -> None:
        """Adjust the polling interval based on current device state.

        This implements adaptive polling:
        - 30 seconds when light is on (responsive updates)
        - 5 minutes when light is off (save resources)
        - 15 minutes when device unavailable (minimal polling)
        """
        new_interval = self._get_adaptive_interval()
        new_state = self._get_poll_state()

        # Only log and update if the interval actually changed
        if new_state != self._last_poll_state:
            LOGGER.debug(
                "Adaptive polling for %s: state=%s -> %s, interval=%ds",
                self.instance.mac,
                self._last_poll_state,
                new_state,
                int(new_interval.total_seconds()),
            )
            self._last_poll_state = new_state
            self.update_interval = new_interval

    def _get_current_data(self) -> dict[str, Any]:
        """Get current device state as dictionary.

        Returns:
            Dictionary containing all device state data
        """
        return {
            # Power state
            "is_on": self.instance.is_on,
            "available": self.instance.available,
            "ble_available": self.instance.ble_available,
            "connected": self.instance.is_connected,
            # Light state
            "color_mode": self.instance.color_mode,
            "color_on": self.instance.color_on,
            "white_on": self.instance.white_on,
            "white_brightness": self.instance.white_brightness,
            "color_brightness": self.instance.color_brightness,
            "rgb_color": self.instance.rgb_color,
            "effect": self.instance.effect,
            # Diagnostics
            "rssi": self.instance.rssi,
            "last_seen": self.instance.last_seen,
            "last_raw_notification": self.instance.last_raw_notification,
            # Timer
            "timer_active": self.instance.timer_active,
            "timer_minutes": self.instance.timer_minutes,
            # Therapy tracking
            "therapy_today_minutes": self.instance.therapy_today_minutes,
            "therapy_week_minutes": self.instance.therapy_week_minutes,
            "therapy_goal_reached": self.instance.therapy_goal_reached,
            "therapy_goal_progress_pct": self.instance.therapy_goal_progress_pct,
            "therapy_daily_goal": self.instance.therapy_daily_goal,
            # Connection health metrics
            "reconnect_count": self.instance.reconnect_count,
            "command_success_rate": self.instance.command_success_rate,
            "connection_uptime": self.instance.connection_uptime_seconds,
            "total_commands": self.instance.total_commands,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from device (periodic refresh).

        This is called periodically by the coordinator to ensure
        state consistency. For BLE devices, this triggers a status
        request if connected.

        Returns:
            Current device state

        Raises:
            UpdateFailed: If update fails
        """
        LOGGER.debug("Periodic refresh for %s", self.instance.mac)

        try:
            # Only actively update if device is available
            if self.instance.ble_available:
                await self.instance.update()
            else:
                LOGGER.debug(
                    "Skipping update - device %s not BLE available",
                    self.instance.mac,
                )

            data = self._get_current_data()

            # Adjust polling interval after each update
            self._adjust_polling_interval()

            return data

        except Exception as err:
            LOGGER.debug(
                "Update failed for %s: %s",
                self.instance.mac,
                err,
            )
            # Adjust polling interval even on failure
            self._adjust_polling_interval()

            # Don't raise UpdateFailed for BLE - device might be temporarily
            # out of range, and we don't want to mark entities unavailable
            # The availability is managed by the BLE stack
            return self._get_current_data()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator.

        Called when the config entry is unloaded.
        """
        self.instance.remove_update_callback(self._handle_push_update)
        await super().async_shutdown()

    # Convenience properties for entity access
    @property
    def is_on(self) -> bool | None:
        """Return if light is on."""
        return self.data.get("is_on") if self.data else None

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self.data.get("available", False) if self.data else False

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        return self.data.get("color_mode", ColorMode.WHITE) if self.data else ColorMode.WHITE

    @property
    def brightness(self) -> int | None:
        """Return current brightness based on mode."""
        if not self.data:
            return None
        if self.data.get("color_mode") == ColorMode.WHITE:
            return self.data.get("white_brightness")
        return self.data.get("color_brightness")

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return RGB color."""
        return self.data.get("rgb_color") if self.data else None

    @property
    def effect(self) -> str | None:
        """Return current effect."""
        return self.data.get("effect") if self.data else None

    @property
    def rssi(self) -> int | None:
        """Return RSSI signal strength."""
        return self.data.get("rssi") if self.data else None

    @property
    def current_poll_interval(self) -> int:
        """Return current polling interval in seconds."""
        if self.update_interval:
            return int(self.update_interval.total_seconds())
        return POLL_INTERVAL_LIGHT_OFF

    @property
    def poll_state(self) -> str:
        """Return current polling state (on/off/unavailable)."""
        return self._last_poll_state
