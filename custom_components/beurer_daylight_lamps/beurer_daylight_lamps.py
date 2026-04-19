"""Beurer Daylight Lamp BLE communication module.

This module handles BLE communication with Beurer TL50/TL70/TL80/TL90/TL100 daylight lamps.

Protocol Overview:
- Commands are sent as packets with header, length, payload, checksum, and trailer
- Packet structure: [0xFE, 0xEF, 0x0A, length, 0xAB, 0xAA, payload_len, ...payload..., checksum, 0x55, 0x0D, 0x0A]

Command bytes (first byte of payload):
- 0x30: Request status
- 0x31: Set brightness (0-100%)
- 0x32: Set RGB color
- 0x34: Set effect
- 0x35: Turn off
- 0x37: Set mode (white=0x01, rgb=0x02)

Notification versions (byte 8 of response):
- 1: White mode status
- 2: RGB mode status
- 255: Device off
- 0: Device shutdown
"""

from __future__ import annotations

import asyncio
import datetime
import time
from typing import TYPE_CHECKING, Any

from bleak import BleakClient  # noqa: TC002 - needed at runtime for test mocking
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.light import ColorMode  # type: ignore[attr-defined]

from .therapy import SunriseSimulation, TherapyTracker
from .wl90 import WL90Controller

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from bleak.backends.characteristic import BleakGATTCharacteristic
    from bleak.backends.device import BLEDevice
    from homeassistant.core import HomeAssistant

from .const import (
    # Adapter failure constants
    ADAPTER_FAILURE_COOLDOWN,
    CMD_ALARM_SYNC,
    CMD_BRIGHTNESS,
    CMD_COLOR,
    # Protocol commands
    CMD_DEVICE_PERMISSION,
    CMD_EFFECT,
    CMD_MODE,
    CMD_MUSIC_QUERY,
    CMD_OFF,
    CMD_RADIO_SYNC_STATUS,
    CMD_SETTINGS_READ,
    CMD_SETTINGS_WRITE,
    CMD_STATUS,
    # APK-discovered commands
    CMD_TIME_SYNC,
    CMD_TIMER_CANCEL,
    CMD_TIMER_TOGGLE,
    CMD_TIMER_VALUE,
    # Timing constants
    COMMAND_DELAY,
    COMMAND_TIMEOUT,
    CONNECTION_STALE_TIMEOUT,
    # Connection health constants
    CONNECTION_WATCHDOG_INTERVAL,
    EFFECT_DELAY,
    LOGGER,
    MIN_COMMAND_INTERVAL,
    MODE_CHANGE_DELAY,
    MODE_RGB,
    MODE_WHITE,
    READ_CHARACTERISTIC_UUID,
    RECONNECT_BACKOFF_MULTIPLIER,
    # Reconnection constants
    RECONNECT_INITIAL_BACKOFF,
    RECONNECT_MAX_BACKOFF,
    RECONNECT_MIN_INTERVAL,
    # Response command bytes
    RESP_DEVICE_PERMISSION,
    RESP_LIGHT_TIMER_END,
    RESP_MOONLIGHT_TIMER_END,
    RESP_SETTINGS_FROM_DEVICE,
    RESP_SETTINGS_SYNC,
    STATUS_DELAY,
    SUPPORTED_EFFECTS,
    TURN_OFF_DELAY,
    WRITE_CHARACTERISTIC_UUID,
    is_wl_model,
)


class BeurerInstance:
    """Representation of a Beurer daylight lamp BLE device."""

    def __init__(
        self,
        device: BLEDevice,
        rssi: int | None = None,
        hass: HomeAssistant | None = None,
    ) -> None:
        """Initialize the Beurer instance.

        Args:
            device: BLE device from Home Assistant's Bluetooth stack
            rssi: Initial RSSI value (signal strength)
            hass: Home Assistant instance for accessing Bluetooth APIs
        """
        if device is None:
            raise ValueError("Cannot initialize BeurerInstance with None device")
        if not hasattr(device, "address"):
            raise ValueError(f"Invalid device object: {device}")

        self._mac: str = device.address
        self._ble_device: BLEDevice = device
        self._hass: HomeAssistant | None = hass
        self._client: BleakClient | None = None
        self._update_callbacks: list[Callable[[], None]] = []
        self._rssi: int | None = rssi

        # Light state
        self._available: bool = False
        self._light_on: bool = False
        self._color_on: bool = False
        self._rgb_color: tuple[int, int, int] = (255, 255, 255)
        self._brightness: int | None = None
        self._color_brightness: int | None = None
        self._effect: str = "Off"
        self._write_uuid: str | None = None
        self._read_uuid: str | None = None
        self._mode: ColorMode = ColorMode.WHITE
        self._supported_effects: list[str] = list(SUPPORTED_EFFECTS)
        self._mode_switch_target: ColorMode | None = None

        # Connection and timing state
        self._last_command_time: float = 0.0
        self._last_seen: float = time.time()
        self._ble_available: bool = True
        self._ever_connected: bool = False

        # Diagnostic state
        self._last_raw_notification: str | None = None
        self._last_unknown_notification: str | None = None
        self._last_notification_version: int | None = None
        self._heartbeat_count: int = 0
        self._timer_active: bool = False
        self._timer_minutes: int | None = None
        self._device_permission_granted: bool = False

        # Device settings (from APK reverse engineering)
        self._feedback_enabled: bool | None = None
        self._fade_enabled: bool | None = None
        self._display_setting: int = 0
        self._date_format: int = 0
        self._time_format: int = 0

        # Connection health and reconnection
        self._init_connection_state()

        # Therapy tracking and WL90
        self._sunrise_simulation: SunriseSimulation | None = None
        self._therapy_tracker: TherapyTracker = TherapyTracker()
        self.adaptive_lighting_switch: Any = None
        self._is_wl: bool = is_wl_model(getattr(device, "name", None))
        self._wl90: WL90Controller | None = (
            WL90Controller(self) if self._is_wl else None
        )

    def _init_connection_state(self) -> None:
        """Initialize connection health and reconnection state."""
        self._reconnect_lock: asyncio.Lock = asyncio.Lock()
        self._reconnect_backoff: float = RECONNECT_INITIAL_BACKOFF
        self._last_reconnect_attempt: float = 0.0
        self._adapter_failures: dict[str, float] = {}
        self._watchdog_task: asyncio.Task[None] | None = None
        self._reconnect_count: int = 0
        self._command_success_count: int = 0
        self._command_failure_count: int = 0
        self._connection_start_time: float | None = None
        self._reconnect_loop_active: bool = False

    def update_ble_device(self, device: BLEDevice) -> None:
        """Update the BLE device reference.

        This is called when a better adapter (e.g., closer proxy) is available.
        """
        if device and device.address == self._mac:
            old_device = self._ble_device
            self._ble_device = device
            LOGGER.debug(
                "Updated BLE device reference for %s (was: %s, now: %s)",
                self._mac,
                getattr(old_device, "name", "unknown"),
                getattr(device, "name", "unknown"),
            )

    def mark_seen(self) -> None:
        """Mark the device as seen (received advertisement)."""
        self._last_seen = time.time()
        was_ble_unavailable = not self._ble_available

        if was_ble_unavailable:
            LOGGER.info("Device %s is now reachable again", self._mac)
            self._ble_available = True
            # Reset backoff when device becomes reachable again
            self._reconnect_backoff = RECONNECT_INITIAL_BACKOFF
            self._safe_create_task(
                self._trigger_update(), "beurer_ble_reachable_update"
            )

        # Auto-reconnect if device needs it
        # The _auto_reconnect method is thread-safe and handles the lock internally
        should_reconnect = not self.is_connected and (
            was_ble_unavailable or not self._available
        )

        # Apply cooldown to prevent queueing too many reconnect attempts
        # from frequent BLE advertisements
        now = time.time()
        if (
            should_reconnect
            and (now - self._last_reconnect_attempt) < RECONNECT_MIN_INTERVAL
        ):
            LOGGER.debug(
                "Device %s reconnect skipped - cooldown active (%.1fs remaining)",
                self._mac,
                RECONNECT_MIN_INTERVAL - (now - self._last_reconnect_attempt),
            )
            should_reconnect = False

        if should_reconnect:
            LOGGER.debug(
                "Device %s needs reconnect (was_ble_unavailable=%s, is_connected=%s, _available=%s)",
                self._mac,
                was_ble_unavailable,
                self.is_connected,
                self._available,
            )
            self._safe_create_task(self._auto_reconnect(), "beurer_auto_reconnect")

    def mark_unavailable(self) -> None:
        """Mark the device as unavailable (not seen by any adapter)."""
        if self._ble_available:
            LOGGER.debug(
                "Device %s marked as unavailable (no BLE advertisements)", self._mac
            )
            self._ble_available = False
            self._available = False
            self._safe_create_task(self._trigger_update(), "beurer_unavailable_update")

    async def _auto_reconnect(self) -> None:
        """Automatically reconnect when device becomes available again.

        Runs as a persistent retry loop with exponential backoff to avoid
        overwhelming the BLE stack. The loop keeps retrying until:
        - Connection succeeds
        - Device becomes BLE unavailable (powered off / out of range)
        - Task is cancelled

        The backoff is reset when:
        - Connection succeeds
        - Device becomes BLE reachable again after being unavailable

        Uses asyncio.Lock per-iteration to prevent parallel connection attempts
        while allowing external state updates (mark_seen) between retries.

        Only one reconnect loop runs at a time. If a loop is already active,
        new calls return immediately (the running loop will pick up state changes).
        """
        # Prevent duplicate reconnect loops
        if self._reconnect_loop_active:
            LOGGER.debug(
                "Auto-reconnect to %s skipped - loop already active",
                self._mac,
            )
            return

        self._reconnect_loop_active = True
        max_attempts = 0  # Safety counter for logging

        try:
            while True:
                max_attempts += 1

                async with self._reconnect_lock:
                    # Check if reconnect is still needed
                    if self._available or self.is_connected:
                        LOGGER.debug(
                            "Auto-reconnect to %s skipped - already connected",
                            self._mac,
                        )
                        self._reconnect_backoff = RECONNECT_INITIAL_BACKOFF
                        return

                    # Check if device is BLE reachable
                    if not self._ble_available:
                        LOGGER.debug(
                            "Auto-reconnect to %s stopped - device not BLE reachable",
                            self._mac,
                        )
                        return

                    self._last_reconnect_attempt = time.time()

                    LOGGER.debug(
                        "Auto-reconnect to %s attempt #%d (backoff: %.1fs)",
                        self._mac,
                        max_attempts,
                        self._reconnect_backoff,
                    )

                # Sleep OUTSIDE the lock so mark_seen() can update state
                await asyncio.sleep(self._reconnect_backoff)

                # Re-check conditions after delay (state may have changed during sleep)
                # Note: mypy thinks these are unreachable because it doesn't understand
                # that state can change during await. These checks ARE necessary.
                if self._available or self.is_connected or not self._ble_available:
                    reason = (  # type: ignore[unreachable]
                        "connected during backoff"
                        if (self._available or self.is_connected)
                        else "device became unreachable"
                    )
                    LOGGER.debug(
                        "Auto-reconnect to %s cancelled - %s",
                        self._mac,
                        reason,
                    )
                    if self._available or self.is_connected:
                        self._reconnect_backoff = RECONNECT_INITIAL_BACKOFF
                    return

                LOGGER.debug(
                    "Auto-reconnecting to %s (attempt #%d)", self._mac, max_attempts
                )

                try:
                    async with self._reconnect_lock:
                        # Final check inside lock before connecting
                        # State can change between the earlier checks and lock acquisition
                        if self._available or self.is_connected:
                            self._reconnect_backoff = RECONNECT_INITIAL_BACKOFF  # type: ignore[unreachable]
                            return

                        connected = await self.connect()

                    if connected:
                        LOGGER.info(
                            "Auto-reconnect to %s successful (attempt #%d)",
                            self._mac,
                            max_attempts,
                        )
                        self._reconnect_backoff = RECONNECT_INITIAL_BACKOFF
                        return  # Success - exit the loop

                    # Failed - increase backoff and retry
                    self._reconnect_backoff = min(
                        self._reconnect_backoff * RECONNECT_BACKOFF_MULTIPLIER,
                        RECONNECT_MAX_BACKOFF,
                    )
                    LOGGER.debug(
                        "Auto-reconnect to %s failed (attempt #%d), retrying in %.1fs",
                        self._mac,
                        max_attempts,
                        self._reconnect_backoff,
                    )

                except asyncio.CancelledError:
                    LOGGER.debug("Auto-reconnect to %s cancelled", self._mac)
                    raise  # Re-raise to properly handle cancellation

                except (BleakError, TimeoutError, OSError) as err:
                    self._reconnect_backoff = min(
                        self._reconnect_backoff * RECONNECT_BACKOFF_MULTIPLIER,
                        RECONNECT_MAX_BACKOFF,
                    )
                    LOGGER.warning(
                        "Auto-reconnect to %s failed (attempt #%d): %s (retrying in %.1fs)",
                        self._mac,
                        max_attempts,
                        err,
                        self._reconnect_backoff,
                    )

        finally:
            self._reconnect_loop_active = False

    @property
    def ble_available(self) -> bool:
        """Return True if device is reachable via Bluetooth.

        Device is reachable if:
        - Currently connected (GATT connection active), OR
        - Seen in BLE advertisements
        """
        # If connected, device is definitely reachable
        if self.is_connected:
            return True
        return self._ble_available

    @property
    def last_seen(self) -> float:
        """Return timestamp when device was last seen."""
        return self._last_seen

    @property
    def last_raw_notification(self) -> str | None:
        """Return the last raw notification hex string (for diagnostics)."""
        return self._last_raw_notification

    @property
    def last_unknown_notification(self) -> str | None:
        """Return the last unknown notification hex string (for reverse engineering)."""
        return self._last_unknown_notification

    @property
    def last_notification_version(self) -> int | None:
        """Return the version byte of the last notification."""
        return self._last_notification_version

    @property
    def heartbeat_count(self) -> int:
        """Return the number of heartbeat/ACK packets received."""
        return self._heartbeat_count

    @property
    def timer_active(self) -> bool:
        """Return True if timer is currently active."""
        return self._timer_active

    @property
    def timer_minutes(self) -> int | None:
        """Return remaining timer minutes if active."""
        return self._timer_minutes if self._timer_active else None

    @property
    def is_wl(self) -> bool:
        """Return True if this device is a WL model (supports radio/alarm/music)."""
        return self._is_wl

    @property
    def wl90(self) -> WL90Controller | None:
        """Return the WL90 controller, or None if not a WL90 device."""
        return self._wl90

    # Device settings properties (from APK reverse engineering)
    @property
    def feedback_enabled(self) -> bool | None:
        """Return True if device feedback sound is enabled, None if unknown."""
        return self._feedback_enabled

    @property
    def fade_enabled(self) -> bool | None:
        """Return True if smooth fade transitions are enabled, None if unknown."""
        return self._fade_enabled

    # Therapy tracking properties
    @property
    def sunrise_simulation(self) -> SunriseSimulation:
        """Return the sunrise simulation controller."""
        if self._sunrise_simulation is None:
            self._sunrise_simulation = SunriseSimulation(self, self._hass)
        return self._sunrise_simulation

    @property
    def therapy_tracker(self) -> TherapyTracker:
        """Return the therapy tracker."""
        return self._therapy_tracker

    @property
    def therapy_today_minutes(self) -> float:
        """Return therapy minutes accumulated today."""
        return self._therapy_tracker.today_minutes

    @property
    def therapy_week_minutes(self) -> float:
        """Return therapy minutes accumulated this week."""
        return self._therapy_tracker.week_minutes

    @property
    def therapy_goal_reached(self) -> bool:
        """Return True if daily therapy goal is reached."""
        return self._therapy_tracker.goal_reached

    @property
    def therapy_goal_progress_pct(self) -> int:
        """Return progress towards daily goal as percentage."""
        return self._therapy_tracker.goal_progress_pct

    @property
    def therapy_daily_goal(self) -> int:
        """Return daily goal in minutes."""
        return self._therapy_tracker.daily_goal_minutes

    def set_therapy_daily_goal(self, minutes: int) -> None:
        """Set the daily therapy goal.

        Args:
            minutes: Goal in minutes (will be clamped to 1-120 range)
        """
        clamped = max(1, min(120, minutes))
        if clamped != minutes:
            LOGGER.warning(
                "Therapy goal %d minutes clamped to valid range: %d minutes",
                minutes,
                clamped,
            )
        self._therapy_tracker.daily_goal_minutes = clamped
        LOGGER.debug("Set therapy daily goal to %d minutes", clamped)
        self._safe_create_task(self._trigger_update(), "beurer_therapy_goal_update")

    # Connection health metrics properties
    @property
    def reconnect_count(self) -> int:
        """Return the total number of reconnections since startup."""
        return self._reconnect_count

    @property
    def command_success_rate(self) -> int:
        """Return command success rate as percentage (0-100)."""
        total = self._command_success_count + self._command_failure_count
        if total == 0:
            return 100  # No commands yet, assume 100%
        return int(self._command_success_count / total * 100)

    @property
    def connection_uptime_seconds(self) -> int | None:
        """Return seconds since current connection was established."""
        if self._connection_start_time is None or not self.is_connected:
            return None
        return int(time.time() - self._connection_start_time)

    @property
    def total_commands(self) -> int:
        """Return total number of commands sent."""
        return self._command_success_count + self._command_failure_count

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection callback."""
        LOGGER.info("Disconnected from %s - will attempt reconnect", self._mac)
        self._available = False
        self._light_on = False
        self._color_on = False
        self._write_uuid = None
        self._read_uuid = None
        self._connection_start_time = None  # Clear connection uptime

        # Stop the connection watchdog
        self._stop_watchdog()

        if self._update_callbacks:
            self._safe_create_task(self._trigger_update(), "beurer_disconnect_update")

        # Trigger auto-reconnect after disconnect (if device is still BLE reachable)
        # The _auto_reconnect method is thread-safe and handles concurrency internally
        if self._ble_available:
            LOGGER.debug(
                "Device %s still BLE reachable, scheduling reconnect", self._mac
            )
            self._safe_create_task(
                self._auto_reconnect(), "beurer_disconnect_reconnect"
            )

    def _safe_create_task(
        self, coro: Coroutine[Any, Any, None], name: str | None = None
    ) -> asyncio.Task[None] | None:
        """Create an asyncio task with error handling.

        This prevents unhandled exceptions in fire-and-forget tasks from
        being silently lost. Uses Home Assistant's task creation when available.

        Args:
            coro: The coroutine to run
            name: Optional name for the task (for debugging)

        Returns:
            The created task, or None if task creation failed.
        """
        task_name = name or f"beurer_task_{self._mac}"

        async def _wrapped() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                LOGGER.debug(
                    "Background task '%s' cancelled for %s", task_name, self._mac
                )
                raise  # Re-raise to properly signal cancellation
            except (BleakError, TimeoutError, OSError) as err:
                LOGGER.error(
                    "Error in background task '%s' for %s: %s",
                    task_name,
                    self._mac,
                    err,
                )

        try:
            # Prefer Home Assistant's task creation if available
            if self._hass is not None:
                return self._hass.async_create_background_task(
                    _wrapped(),
                    task_name,
                )
            # Fallback for standalone usage
            return asyncio.create_task(_wrapped(), name=task_name)
        except RuntimeError:
            # No event loop running (e.g., during shutdown)
            LOGGER.debug(
                "Could not create task '%s' - no event loop running", task_name
            )
            return None

    def _start_watchdog(self) -> None:
        """Start the connection watchdog task.

        The watchdog monitors connection health and triggers reconnection
        if the connection becomes stale (no data received for too long).
        """
        self._stop_watchdog()  # Cancel any existing watchdog

        async def _watchdog_loop() -> None:
            """Periodically check connection health."""
            try:
                while True:
                    try:
                        await asyncio.sleep(CONNECTION_WATCHDOG_INTERVAL)

                        if not self.is_connected:
                            LOGGER.debug(
                                "Watchdog: %s not connected, stopping", self._mac
                            )
                            break

                        time_since_data = time.time() - self._last_seen
                        if time_since_data > CONNECTION_STALE_TIMEOUT:
                            LOGGER.warning(
                                "Watchdog: Connection to %s appears stale (%.0fs without data), forcing reconnect",
                                self._mac,
                                time_since_data,
                            )
                            # Disconnect and let auto-reconnect handle it
                            await self.disconnect()
                            if self._ble_available:
                                self._safe_create_task(
                                    self._auto_reconnect(),
                                    "beurer_watchdog_reconnect",
                                )
                            break
                        LOGGER.debug(
                            "Watchdog: %s healthy (last data %.0fs ago)",
                            self._mac,
                            time_since_data,
                        )

                    except asyncio.CancelledError:
                        LOGGER.debug("Watchdog: %s cancelled", self._mac)
                        raise  # Re-raise to exit the loop

                    except (BleakError, TimeoutError, OSError) as err:
                        LOGGER.error("Watchdog: Error for %s: %s", self._mac, err)
                        break  # Exit loop on unexpected error

            finally:
                # Clear task reference when loop exits
                self._watchdog_task = None
                LOGGER.debug("Watchdog: %s exited", self._mac)

        # Store task reference for proper cleanup
        self._watchdog_task = self._safe_create_task(
            _watchdog_loop(),
            f"beurer_watchdog_{self._mac}",
        )
        if self._watchdog_task:
            LOGGER.debug("Started connection watchdog for %s", self._mac)

    def _stop_watchdog(self) -> None:
        """Stop the connection watchdog task."""
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            # Don't set to None here - the finally block in the task will do it
            LOGGER.debug("Stopping connection watchdog for %s", self._mac)

    def set_update_callback(self, callback: Callable[[], None] | None) -> None:
        """Register or unregister a callback for state updates."""
        if callback is None:
            return
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[], None]) -> None:
        """Remove a callback from state updates."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    @property
    def mac(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    def is_on(self) -> bool | None:
        """Return True if lamp is on, None if unknown/unavailable.

        This is derived from the internal _light_on and _color_on state.
        Returns None when device state is unknown (not yet connected or disconnected).
        """
        if not self._available:
            return None
        return self._light_on or self._color_on

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the RGB color."""
        return self._rgb_color

    @property
    def color_brightness(self) -> int | None:
        """Return the color mode brightness."""
        return self._color_brightness

    @property
    def white_brightness(self) -> int | None:
        """Return the white mode brightness."""
        return self._brightness

    @property
    def effect(self) -> str:
        """Return the current effect."""
        return self._effect

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        return self._mode

    def set_color_mode(self, mode: ColorMode) -> None:
        """Set the color mode.

        This is used by the light platform to prepare the mode before sending commands.
        """
        self._mode = mode

    @property
    def supported_effects(self) -> list[str]:
        """Return list of supported effects."""
        return self._supported_effects

    @property
    def color_on(self) -> bool:
        """Return True if color/RGB mode is active.

        This property exposes the internal color state for use by
        the light platform when determining which mode is active.
        """
        return self._color_on

    @property
    def white_on(self) -> bool:
        """Return True if white mode is active.

        This property exposes the internal white state for use by
        the light platform when determining which mode is active.
        """
        return self._light_on

    @property
    def rssi(self) -> int | None:
        """Return the RSSI signal strength."""
        return self._rssi

    def update_rssi(self, rssi: int | None) -> None:
        """Update the RSSI value."""
        if rssi is not None and rssi != self._rssi:
            self._rssi = rssi
            LOGGER.debug("Updated RSSI for %s: %d dBm", self._mac, rssi)

    @property
    def available(self) -> bool:
        """Return True if device is available for commands.

        Device is available if:
        - Connected via GATT (active connection), OR
        - Reachable via BLE AND we've received status, OR
        - Was previously connected (commands will trigger reconnect)
        """
        if self.is_connected:
            return True
        if self.ble_available and self._available:
            return True
        # Keep available after disconnect so HA allows commands through.
        # _send_packet handles reconnection transparently before sending.
        return self._ever_connected

    @property
    def is_connected(self) -> bool:
        """Return True if connected to the device."""
        return self._client.is_connected if self._client else False

    @property
    def write_uuid(self) -> str | None:
        """Return the write characteristic UUID."""
        return self._write_uuid

    @property
    def read_uuid(self) -> str | None:
        """Return the read characteristic UUID."""
        return self._read_uuid

    def _find_effect_index(self, effect: str | None) -> int:
        """Find the index of an effect."""
        if effect is None:
            return 0
        try:
            return self._supported_effects.index(effect)
        except ValueError:
            LOGGER.debug(
                "Effect '%s' not in supported list, defaulting to 'Off'", effect
            )
            return 0

    def _calculate_checksum(self, length: int, data: list[int]) -> int:
        """Calculate packet checksum."""
        result = length
        for byte in data:
            result ^= byte
        return result

    async def _write(self, data: bytearray) -> bool:
        """Write data to the device.

        Args:
            data: The bytearray to write to the device

        Returns:
            True if write was successful, False otherwise.
        """
        if not self._client or not self._client.is_connected:
            LOGGER.debug("Device not connected, attempting reconnect for write")
            if not await self.connect():
                LOGGER.debug("Failed to reconnect for write to %s", self._mac)
                self._command_failure_count += 1
                return False

        # Safety check after reconnect (for type checker)
        if self._client is None:
            self._command_failure_count += 1
            return False

        if not self._write_uuid:
            LOGGER.error("Write UUID not available")
            self._command_failure_count += 1
            return False

        try:
            LOGGER.debug(
                "Writing to %s: %s",
                self._mac,
                data.hex(),
            )
            # Explicit 6s timeout matching Beurer LightUp APK's
            # TimeOutRequestProxy (bleak default is ~30s)
            await asyncio.wait_for(
                self._client.write_gatt_char(self._write_uuid, data),
                timeout=COMMAND_TIMEOUT,
            )
        except TimeoutError:
            LOGGER.warning(
                "Command timeout (%.0fs) writing to %s",
                COMMAND_TIMEOUT,
                self._mac,
            )
            self._command_failure_count += 1
            await self.disconnect()
            return False
        except (BleakError, OSError) as err:
            LOGGER.debug("Error during write to %s: %s", self._mac, err)
            self._command_failure_count += 1
            await self.disconnect()
            return False
        else:
            self._command_success_count += 1
            return True

    async def _send_packet(self, message: list[int]) -> bool:
        """Send a command packet to the device.

        Includes rate limiting to prevent overwhelming the device with
        rapid command sequences.

        Args:
            message: List of command bytes to send

        Returns:
            True if packet was sent successfully, False otherwise.
        """
        if (
            not self._client or not self._client.is_connected
        ) and not await self.connect():
            return False

        # Rate limiting: ensure minimum interval between commands
        now = time.monotonic()
        elapsed = now - self._last_command_time
        if elapsed < MIN_COMMAND_INTERVAL:
            await asyncio.sleep(MIN_COMMAND_INTERVAL - elapsed)

        length = len(message)
        plen = length + 2  # payload_len includes command bytes + checksum

        # Calculate checksum: plen XOR all command bytes
        checksum = plen
        for byte in message:
            checksum ^= byte

        # Packet format from btsnoop analysis:
        # - Header: FE EF 0A
        # - outer_len = command_len + 7
        # - Magic: AB AA
        # - payload_len = command_len + 2 (includes checksum)
        # - Command bytes
        # - Checksum: plen XOR cmd_bytes
        # - Trailer: 55 0D 0A
        packet = bytearray(
            [
                0xFE,
                0xEF,
                0x0A,
                length + 7,
                0xAB,
                0xAA,
                plen,
                *message,
                checksum,
                0x55,
                0x0D,
                0x0A,
            ]
        )

        result = await self._write(packet)
        self._last_command_time = time.monotonic()
        return result

    async def set_color(
        self, rgb: tuple[int, int, int], _from_turn_on: bool = False
    ) -> None:
        """Set RGB color.

        Args:
            rgb: Tuple of (red, green, blue) values (0-255 each)
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        # Ensure RGB values are integers (color_temperature_to_rgb may return floats)
        r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
        LOGGER.debug("Setting color R=%d, G=%d, B=%d for %s", r, g, b, self._mac)

        self._mode = ColorMode.RGB
        self._rgb_color = (r, g, b)

        self._mode_switch_target = ColorMode.RGB
        try:
            # Activate RGB mode if not already active
            if not self._color_on:
                LOGGER.debug("Activating RGB mode")
                await self._send_packet([CMD_MODE, MODE_RGB])
                await asyncio.sleep(MODE_CHANGE_DELAY)
                self._color_on = True
                self._light_on = False
                self._available = True
                # Only set effect to Off if we're switching modes
                if self._effect != "Off":
                    self._effect = "Off"
                    await self._send_packet([CMD_EFFECT, 0])
                    await asyncio.sleep(COMMAND_DELAY)

            await self._send_packet([CMD_COLOR, r, g, b])
            await asyncio.sleep(COMMAND_DELAY)
            await self._request_status()
        finally:
            self._mode_switch_target = None

    async def set_color_with_brightness(
        self,
        rgb: tuple[int, int, int],
        brightness: int | None = None,
    ) -> None:
        """Set RGB color and brightness atomically.

        This method combines color and brightness setting to avoid
        intermediate states where the color changes but brightness is wrong.

        Args:
            rgb: Tuple of (red, green, blue) values (0-255 each)
            brightness: Brightness value (0-255), or None to keep current
        """
        r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
        LOGGER.debug(
            "Setting color R=%d, G=%d, B=%d with brightness=%s for %s",
            r,
            g,
            b,
            brightness,
            self._mac,
        )

        self._mode = ColorMode.RGB
        self._rgb_color = (r, g, b)

        self._mode_switch_target = ColorMode.RGB
        try:
            # Activate RGB mode if not already active
            if not self._color_on:
                LOGGER.debug("Activating RGB mode")
                await self._send_packet([CMD_MODE, MODE_RGB])
                await asyncio.sleep(MODE_CHANGE_DELAY)
                self._color_on = True
                self._light_on = False
                self._available = True

            # Always clear effect when setting a specific color
            # This ensures no rainbow/animation overrides the color
            if self._effect != "Off":
                LOGGER.debug("Clearing effect (was: %s)", self._effect)
                self._effect = "Off"
                await self._send_packet([CMD_EFFECT, 0])
                await asyncio.sleep(COMMAND_DELAY)

            # Set color
            await self._send_packet([CMD_COLOR, r, g, b])
            await asyncio.sleep(COMMAND_DELAY)

            # Set brightness if provided
            if brightness is not None:
                brightness = int(brightness)
                self._color_brightness = brightness
                brightness_percent = max(0, min(100, int(brightness / 255 * 100)))
                await self._send_packet([CMD_BRIGHTNESS, MODE_RGB, brightness_percent])
                await asyncio.sleep(COMMAND_DELAY)

            # Single status request at the end
            await self._request_status()
        finally:
            self._mode_switch_target = None

    async def set_color_with_brightness_fast(
        self,
        rgb: tuple[int, int, int],
        brightness: int | None = None,
    ) -> None:
        """Set RGB color and brightness with minimal BLE overhead.

        Optimized for rapid sequential updates (like sunrise/sunset simulations).
        Skips redundant mode switches, effect clears, and status requests.

        Args:
            rgb: Tuple of (red, green, blue) values (0-255 each)
            brightness: Brightness value (0-255), or None to keep current
        """
        r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])

        # Only switch mode if not already in RGB mode
        if not self._color_on:
            LOGGER.debug("Fast color: Activating RGB mode")
            # Lightweight guard only around mode-switch part (no _request_status here)
            self._mode_switch_target = ColorMode.RGB
            try:
                await self._send_packet([CMD_MODE, MODE_RGB])
                await asyncio.sleep(MODE_CHANGE_DELAY)
                self._color_on = True
                self._light_on = False
                self._mode = ColorMode.RGB

                # Clear effect only on first call (mode switch)
                if self._effect != "Off":
                    LOGGER.debug("Fast color: Clearing effect")
                    self._effect = "Off"
                    await self._send_packet([CMD_EFFECT, 0])
                    await asyncio.sleep(COMMAND_DELAY)
            finally:
                self._mode_switch_target = None

        # Update internal state
        self._rgb_color = (r, g, b)
        self._available = True

        # Set color
        await self._send_packet([CMD_COLOR, r, g, b])
        await asyncio.sleep(COMMAND_DELAY)

        # Set brightness if provided
        if brightness is not None:
            brightness = int(brightness)
            self._color_brightness = brightness
            brightness_percent = max(0, min(100, int(brightness / 255 * 100)))
            await self._send_packet([CMD_BRIGHTNESS, MODE_RGB, brightness_percent])
            await asyncio.sleep(COMMAND_DELAY)

        # No status request - caller can request if needed

    async def set_color_brightness(
        self, brightness: float | None, _from_turn_on: bool = False
    ) -> None:
        """Set color mode brightness (0-255).

        Args:
            brightness: Brightness value (0-255), defaults to 255 if None
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        brightness = 255 if brightness is None else int(brightness)

        LOGGER.debug("Setting color brightness to %d for %s", brightness, self._mac)
        self._color_brightness = brightness

        self._mode_switch_target = ColorMode.RGB
        try:
            # If not in RGB mode, switch to it first
            if not self._color_on:
                LOGGER.debug("Switching to RGB mode for brightness change")
                self._mode = ColorMode.RGB
                await self._send_packet([CMD_MODE, MODE_RGB])
                await asyncio.sleep(MODE_CHANGE_DELAY)
                self._color_on = True
                self._light_on = False
                self._available = True

            brightness_percent = max(0, min(100, int(brightness / 255 * 100)))
            await self._send_packet([CMD_BRIGHTNESS, MODE_RGB, brightness_percent])
            await asyncio.sleep(COMMAND_DELAY)
            await self._request_status()
        finally:
            self._mode_switch_target = None

    async def sync_time(self) -> bool:
        """Sync current time from Home Assistant to the device.

        Sends the current date/time so the device clock stays accurate.
        Format: CMD_TIME_SYNC SEC MIN HOUR WEEKDAY DAY MONTH YEAR(offset from 2000)

        Returns:
            True if time sync command was sent successfully.
        """
        now = datetime.datetime.now(tz=datetime.UTC)
        LOGGER.info(
            "Syncing time to %s: %s", self._mac, now.strftime("%Y-%m-%d %H:%M:%S")
        )

        result = await self._send_packet(
            [
                CMD_TIME_SYNC,
                now.second,
                now.minute,
                now.hour,
                now.isoweekday(),  # 1=Monday, 7=Sunday
                now.day,
                now.month,
                now.year - 2000,
            ]
        )
        if result:
            await asyncio.sleep(COMMAND_DELAY)
        return result

    async def query_settings(self) -> bool:
        """Query device settings (feedback, fade, display, date/time format).

        Response will be handled by _handle_settings_notification.

        Returns:
            True if settings query was sent successfully.
        """
        LOGGER.debug("Querying settings from %s", self._mac)
        result = await self._send_packet([CMD_SETTINGS_READ])
        if result:
            await asyncio.sleep(COMMAND_DELAY)
        return result

    async def set_feedback(self, enabled: bool) -> bool:
        """Set device feedback sound (beep on button press).

        Args:
            enabled: True to enable feedback sound, False to disable.

        Returns:
            True if settings command was sent successfully.
        """
        LOGGER.info("Setting feedback sound to %s on %s", enabled, self._mac)
        # APK inverts the value: 0 = enabled, 1 = disabled
        feedback_value = 0 if enabled else 1
        result = await self._send_packet(
            [
                CMD_SETTINGS_WRITE,
                self._display_setting,
                self._date_format,
                self._time_format,
                feedback_value,
                0 if (self._fade_enabled or self._fade_enabled is None) else 1,
            ]
        )
        if result:
            self._feedback_enabled = enabled
            await asyncio.sleep(COMMAND_DELAY)
            await self._trigger_update()
        return result

    async def set_fade(self, enabled: bool) -> bool:
        """Set smooth fade transitions.

        Args:
            enabled: True to enable fade transitions, False to disable.

        Returns:
            True if settings command was sent successfully.
        """
        LOGGER.info("Setting fade to %s on %s", enabled, self._mac)
        # APK inverts the value: 0 = enabled, 1 = disabled
        fade_value = 0 if enabled else 1
        result = await self._send_packet(
            [
                CMD_SETTINGS_WRITE,
                self._display_setting,
                self._date_format,
                self._time_format,
                0 if (self._feedback_enabled or self._feedback_enabled is None) else 1,
                fade_value,
            ]
        )
        if result:
            self._fade_enabled = enabled
            await asyncio.sleep(COMMAND_DELAY)
            await self._trigger_update()
        return result

    async def set_white(
        self, intensity: float | None, _from_turn_on: bool = False
    ) -> None:
        """Set white light intensity (0-255).

        Args:
            intensity: Intensity value (0-255), defaults to 255 if None
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        intensity = 255 if intensity is None else int(intensity)

        LOGGER.debug("Setting white intensity to %d for %s", intensity, self._mac)
        self._mode = ColorMode.WHITE
        self._brightness = intensity

        # Guard wraps entire sequence: mode switch + brightness + status request.
        # This ensures stale RGB notifications from _request_status() don't
        # overwrite the new white state (fixes sunrise→white race condition).
        self._mode_switch_target = ColorMode.WHITE
        try:
            # Switch to white mode if not already active
            if not self._light_on or self._color_on:
                LOGGER.debug(
                    "Activating white mode (light_on=%s, color_on=%s)",
                    self._light_on,
                    self._color_on,
                )
                await self._send_packet([CMD_MODE, MODE_WHITE])
                await asyncio.sleep(MODE_CHANGE_DELAY)
                self._light_on = True
                self._color_on = False
                self._available = True

            intensity_percent = max(0, min(100, int(intensity / 255 * 100)))
            # Cap at 99% to work around firmware bug where 100% in white mode
            # causes some devices to switch to red/RGB mode (see Deadolus#11)
            if intensity_percent == 100:
                intensity_percent = 99
            await self._send_packet([CMD_BRIGHTNESS, MODE_WHITE, intensity_percent])
            await asyncio.sleep(COMMAND_DELAY)
            await self._request_status()
        finally:
            self._mode_switch_target = None

    async def set_effect(self, effect: str | None, _from_turn_on: bool = False) -> None:
        """Set light effect.

        Args:
            effect: Effect name from supported_effects list, defaults to "Off"
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        if effect is None:
            effect = "Off"

        LOGGER.debug("Setting effect to '%s' for %s", effect, self._mac)
        self._effect = effect

        self._mode_switch_target = ColorMode.RGB
        try:
            # Switch to RGB mode if not already active (effects require RGB mode)
            if not self._color_on:
                LOGGER.debug("Activating RGB mode for effect")
                self._mode = ColorMode.RGB
                await self._send_packet([CMD_MODE, MODE_RGB])
                await asyncio.sleep(MODE_CHANGE_DELAY)
                self._color_on = True
                self._light_on = False
                self._available = True

            await self._send_packet([CMD_EFFECT, self._find_effect_index(effect)])
            await asyncio.sleep(EFFECT_DELAY)
            await self._request_status()
        finally:
            self._mode_switch_target = None

    async def set_timer(self, minutes: int) -> bool:
        """Set auto-off timer to specified duration.

        Timer works in both WHITE and RGB mode. Uses two commands:
        1. 0x33 MODE MINUTES - Set timer duration (slider value)
        2. 0x38 MODE - Toggle timer on

        Args:
            minutes: Timer duration in minutes (1-120)

        Returns:
            True if timer command was sent successfully, False otherwise.
        """
        if not 1 <= minutes <= 120:
            LOGGER.error("Timer minutes must be between 1 and 120, got %d", minutes)
            return False

        # Determine current mode from color_mode (more reliable than _color_on)
        mode_byte = MODE_RGB if self._mode == ColorMode.RGB else MODE_WHITE

        LOGGER.info(
            "Setting timer to %d min for %s (mode=0x%02X, color_mode=%s)",
            minutes,
            self._mac,
            mode_byte,
            self._mode,
        )

        # First toggle timer on: 0x38 MODE
        result = await self._send_packet([CMD_TIMER_TOGGLE, mode_byte])
        if not result:
            return False

        await asyncio.sleep(COMMAND_DELAY)

        # Then set the timer duration: 0x33 MODE MINUTES
        result = await self._send_packet([CMD_TIMER_VALUE, mode_byte, minutes])
        if result:
            self._timer_active = True
            self._timer_minutes = minutes
            await asyncio.sleep(COMMAND_DELAY)
            await self._request_status()
        return result

    async def cancel_timer(self) -> bool:
        """Cancel the auto-off timer.

        Command format: 0x36 MODE (2 bytes).

        Returns:
            True if cancel command was sent successfully, False otherwise.
        """
        mode_byte = MODE_RGB if self._mode == ColorMode.RGB else MODE_WHITE

        LOGGER.info(
            "Cancelling timer for %s (mode=0x%02X, color_mode=%s)",
            self._mac,
            mode_byte,
            self._mode,
        )

        result = await self._send_packet([CMD_TIMER_CANCEL, mode_byte])
        if result:
            self._timer_active = False
            self._timer_minutes = 0
            await asyncio.sleep(COMMAND_DELAY)
            await self._request_status()
        return result

    async def turn_on(self) -> None:
        """Turn on the lamp.

        Uses the currently set color_mode to determine whether to activate
        white mode or RGB mode.
        """
        LOGGER.debug(
            "Turning on %s (mode=%s, is_on=%s)",
            self._mac,
            self._mode,
            self.is_on,
        )

        if (
            not self._client or not self._client.is_connected
        ) and not await self.connect():
            LOGGER.error("Failed to connect for turn_on")
            return

        if self._mode == ColorMode.WHITE:
            await self._send_packet([CMD_MODE, MODE_WHITE])
            await asyncio.sleep(MODE_CHANGE_DELAY)
            self._light_on = True
            self._color_on = False
        else:
            await self._send_packet([CMD_MODE, MODE_RGB])
            await asyncio.sleep(MODE_CHANGE_DELAY)
            self._color_on = True
            self._light_on = False

            if not self._available:
                # First time turning on - restore previous settings
                await asyncio.sleep(MODE_CHANGE_DELAY)
                await self.set_effect(self._effect or "Off", _from_turn_on=True)
                await asyncio.sleep(MODE_CHANGE_DELAY)
                if self._rgb_color != (0, 0, 0):
                    await self.set_color(self._rgb_color, _from_turn_on=True)
                await asyncio.sleep(MODE_CHANGE_DELAY)
                if self._color_brightness:
                    await self.set_color_brightness(
                        self._color_brightness, _from_turn_on=True
                    )

        self._available = True
        await asyncio.sleep(MODE_CHANGE_DELAY)
        await self._request_status()

    async def turn_off(self) -> None:
        """Turn off the lamp.

        Sends off commands for both white and RGB modes to ensure the device
        is fully turned off.
        """
        LOGGER.debug("Turning off %s", self._mac)
        await self._send_packet([CMD_OFF, MODE_WHITE])
        await asyncio.sleep(0.1)
        await self._send_packet([CMD_OFF, MODE_RGB])
        self._light_on = False
        self._color_on = False
        await asyncio.sleep(TURN_OFF_DELAY)
        await self._request_status()

    async def _request_status(self) -> None:
        """Request status update from device.

        Requests status for both white and RGB modes to get complete state.
        """
        LOGGER.debug("Requesting status from %s", self._mac)
        await self._send_packet([CMD_STATUS, MODE_WHITE])
        await asyncio.sleep(STATUS_DELAY)
        await self._send_packet([CMD_STATUS, MODE_RGB])

    async def _trigger_update(self) -> None:
        """Trigger Home Assistant state update."""
        if self._update_callbacks:
            LOGGER.debug("Triggering HA update for %s", self._mac)
            for callback in self._update_callbacks:
                callback()

    def _handle_white_status(self, data: bytearray) -> bool:
        """Handle white mode status notification (version 1).

        Returns:
            True if state changed and UI update is needed.
        """
        changed = False
        new_light_on = data[9] == 1
        new_brightness = int(data[10] * 255 / 100) if new_light_on else None

        if self._light_on != new_light_on or self._brightness != new_brightness:
            changed = True

        self._light_on = new_light_on
        self._brightness = new_brightness
        if self._light_on:
            self._mode = ColorMode.WHITE

        # Parse timer state from notification (APK: data[11]=enabled, data[12]=minutes)
        if len(data) > 12:
            new_timer_active = data[11] == 1
            new_timer_minutes = data[12] if new_timer_active else None
            if (
                self._timer_active != new_timer_active
                or self._timer_minutes != new_timer_minutes
            ):
                self._timer_active = new_timer_active
                self._timer_minutes = new_timer_minutes
                changed = True

        LOGGER.debug(
            "White status: on=%s, brightness=%s, timer=%s/%s",
            self._light_on,
            self._brightness,
            self._timer_active,
            self._timer_minutes,
        )
        return changed

    def _handle_rgb_status(self, data: bytearray) -> bool:
        """Handle RGB mode status notification (version 2).

        Returns:
            True if state changed and UI update is needed.
        """
        changed = False
        new_color_on = data[9] == 1
        new_effect = self._effect
        new_color_brightness = self._color_brightness
        new_rgb = self._rgb_color

        if new_color_on:
            effect_idx = data[16]
            if effect_idx < len(self._supported_effects):
                new_effect = self._supported_effects[effect_idx]
            new_color_brightness = int(data[10] * 255 / 100)
            new_rgb = (data[13], data[14], data[15])

        if (
            self._color_on != new_color_on
            or self._effect != new_effect
            or self._color_brightness != new_color_brightness
            or self._rgb_color != new_rgb
        ):
            changed = True

        self._color_on = new_color_on
        self._effect = new_effect
        self._color_brightness = new_color_brightness
        self._rgb_color = new_rgb
        if self._color_on:
            self._mode = ColorMode.RGB

        # Parse timer state from notification (APK: data[11]=enabled, data[12]=minutes)
        if len(data) > 12:
            new_timer_active = data[11] == 1
            new_timer_minutes = data[12] if new_timer_active else None
            if (
                self._timer_active != new_timer_active
                or self._timer_minutes != new_timer_minutes
            ):
                self._timer_active = new_timer_active
                self._timer_minutes = new_timer_minutes
                changed = True

        LOGGER.debug(
            "RGB status: on=%s, brightness=%s, rgb=%s, effect=%s, timer=%s/%s",
            self._color_on,
            self._color_brightness,
            self._rgb_color,
            self._effect,
            self._timer_active,
            self._timer_minutes,
        )

        # Track therapy exposure based on current RGB state
        self._track_therapy_from_rgb()

        return changed

    def _track_therapy_from_rgb(self) -> None:
        """Track therapy exposure based on current RGB state."""
        # Therapy-relevant light: cool white (high blue component) at high brightness
        if self._color_on and self._color_brightness is not None:
            # Estimate color temperature from RGB (simplified: higher blue = cooler)
            r, g, b = self._rgb_color
            # Cool light has roughly equal R/G and higher relative values
            # Therapy-relevant: bright, balanced white (R~=G~=B with high values)
            is_white_ish = abs(r - g) < 50 and abs(g - b) < 50 and min(r, g, b) > 150
            brightness_pct = int(self._color_brightness / 255 * 100)
            # Estimate kelvin (very rough): white-ish light with high brightness
            estimated_kelvin = 5300 if is_white_ish else 3000
            self._therapy_tracker.update_session(estimated_kelvin, brightness_pct)
            if (
                is_white_ish
                and brightness_pct >= 80
                and not self._therapy_tracker.has_active_session
            ):
                self._therapy_tracker.start_session(estimated_kelvin, brightness_pct)
        elif not self._color_on:
            # End session when color mode turns off
            self._therapy_tracker.end_session()

    def _handle_device_off(self) -> bool:
        """Handle device-off notification (version 255).

        Returns:
            True if state changed and UI update is needed.
        """
        changed = False
        if self._light_on or self._color_on:
            changed = True
            # End therapy session when light turns off
            self._therapy_tracker.end_session()
        self._light_on = False
        self._color_on = False
        LOGGER.debug("Device off notification")
        return changed

    async def _dispatch_command_response(self, resp_cmd: int, data: bytearray) -> bool:
        """Dispatch special command responses (timer end, permission, settings, WL90).

        Returns:
            True if the notification was fully handled and no further processing needed.
        """
        # Timer end notifications (from APK: 0xEB=light, 0xEC=moonlight)
        if resp_cmd in (RESP_LIGHT_TIMER_END, RESP_MOONLIGHT_TIMER_END):
            timer_type = "light" if resp_cmd == RESP_LIGHT_TIMER_END else "moonlight"
            result = data[8] if len(data) > 8 else 0
            LOGGER.info(
                "Timer end notification from %s: type=%s, result=%d (1=off, 2=cancelled)",
                self._mac,
                timer_type,
                result,
            )
            self._timer_active = False
            self._timer_minutes = None
            self._last_seen = time.time()
            if result == 1:
                self._light_on = False
                self._color_on = False
            await self._trigger_update()
            return True

        # Device permission response (from APK: 0xF0)
        if resp_cmd == RESP_DEVICE_PERMISSION:
            permission_value = data[8] if len(data) > 8 else 0
            self._device_permission_granted = permission_value == 2
            if self._device_permission_granted:
                LOGGER.debug("Device permission granted on %s", self._mac)
            else:
                LOGGER.warning(
                    "Device permission DENIED on %s (value=%d). "
                    "Another device may be controlling the lamp.",
                    self._mac,
                    permission_value,
                )
            self._last_seen = time.time()
            return True

        # Settings responses (from APK: 0xE2=read, 0xF2=write confirm)
        if resp_cmd in (RESP_SETTINGS_FROM_DEVICE, RESP_SETTINGS_SYNC):
            self._handle_settings_notification(data)
            return True

        # WL90-specific responses (radio, alarm, music)
        if self._wl90 is not None and self._wl90.handle_notification(resp_cmd, data):
            self._last_seen = time.time()
            await self._trigger_update()
            return True

        return False

    def _is_mode_switch_filtered(self, version: int) -> bool:
        """Check if a notification should be filtered during mode switch.

        Returns:
            True if the notification should be discarded as stale.
        """
        if self._mode_switch_target is None:
            return False

        if (
            self._mode_switch_target == ColorMode.WHITE
            and version == 2  # RGB notification contradicts WHITE target
        ):
            LOGGER.debug(
                "Filtering stale RGB notification (version=%d) during WHITE mode switch",
                version,
            )
            self._last_seen = time.time()
            return True
        if (
            self._mode_switch_target == ColorMode.RGB
            and version == 1  # White notification contradicts RGB target
        ):
            LOGGER.debug(
                "Filtering stale white notification (version=%d) during RGB mode switch",
                version,
            )
            self._last_seen = time.time()
            return True
        return False

    async def _handle_notification(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle BLE notification from device.

        Dispatches to sub-handlers based on packet type:
        - Command responses (timer end, permission, settings, WL90)
        - Heartbeat/ACK packets
        - Status updates (white, RGB, device off, shutdown)
        """
        hex_str = data.hex()
        LOGGER.debug("Notification from %s: %s", self._mac, hex_str)
        self._last_raw_notification = hex_str

        if len(data) < 10:
            LOGGER.debug("Short notification (%d bytes), ignoring", len(data))
            return

        # Dispatch special command responses first
        if len(data) > 7 and await self._dispatch_command_response(data[7], data):
            return

        # Check payload length for heartbeat/ACK packets
        payload_len = data[6] if len(data) > 6 else 0
        if payload_len < 0x08:
            LOGGER.debug(
                "Short payload (%d bytes), likely ACK/heartbeat - not updating state",
                payload_len,
            )
            self._last_seen = time.time()
            self._heartbeat_count += 1
            if not self._available:
                self._available = True
            await self._trigger_update()
            return

        # Version-based status dispatch
        version = data[8]
        self._last_notification_version = version

        if self._is_mode_switch_filtered(version):
            return

        # Shutdown must be handled here (async disconnect)
        if version == 0:
            LOGGER.debug("Device shutting down")
            await self.disconnect()
            return

        trigger_update = self._dispatch_version_status(version, data, hex_str)

        if not self._available:
            self._available = True
            trigger_update = True

        if trigger_update:
            await self._trigger_update()

    def _dispatch_version_status(
        self, version: int, data: bytearray, hex_str: str
    ) -> bool:
        """Dispatch version-based status notifications.

        Returns:
            True if state changed and UI update is needed.
        """
        if version == 1:
            return self._handle_white_status(data)
        if version == 2:
            return self._handle_rgb_status(data)
        if version == 255:
            return self._handle_device_off()
        # Unknown version - store for reverse engineering
        self._last_unknown_notification = hex_str
        LOGGER.warning(
            "Unknown notification version %d from %s: hex=%s len=%d bytes=[%s]",
            version,
            self._mac,
            hex_str,
            len(data),
            ", ".join(f"0x{b:02x}" for b in data),
        )
        if not self._available:
            self._available = True
        return True

    def _handle_settings_notification(self, data: bytearray) -> None:
        """Handle a settings response notification.

        Settings response format (from APK reverse engineering):
        - data[8]: display setting
        - data[9]: date format
        - data[10]: time format
        - data[11]: feedback (inverted: 0=enabled, 1=disabled)
        - data[12]: fade (inverted: 0=enabled, 1=disabled)

        Args:
            data: Raw notification bytes
        """
        if len(data) < 13:
            LOGGER.debug("Settings notification too short (%d bytes)", len(data))
            return

        self._display_setting = data[8]
        self._date_format = data[9]
        self._time_format = data[10]
        # APK inverts feedback/fade: 0 means ON, 1 means OFF
        self._feedback_enabled = data[11] == 0
        self._fade_enabled = data[12] == 0

        LOGGER.info(
            "Settings from %s: display=%d, date_fmt=%d, time_fmt=%d, "
            "feedback=%s, fade=%s",
            self._mac,
            self._display_setting,
            self._date_format,
            self._time_format,
            self._feedback_enabled,
            self._fade_enabled,
        )

        self._last_seen = time.time()
        self._safe_create_task(self._trigger_update(), "beurer_settings_update")

    def _is_gatt_capable_source(self, source: str) -> bool:
        """Check if a Bluetooth source is capable of GATT connections.

        Shelly devices with Bluetooth are only passive scanners and cannot
        establish GATT connections. We need to filter them out.

        GATT-capable sources:
        - ESPHome Bluetooth Proxies (active: true)
        - Local Bluetooth adapters (hci0, bcm43438, etc.)

        Non-GATT sources (passive only):
        - Shelly Plug S Gen3 (and other Shelly devices with BLE)
        - Other passive-only scanners

        Args:
            source: The Bluetooth source identifier

        Returns:
            True if the source is likely capable of GATT connections
        """
        source_lower = source.lower()

        # Known non-GATT sources (Shelly devices are passive only)
        non_gatt_patterns = [
            "shelly",
            "shellyplug",
            "shellypm",
            "shelly1",
            "shelly2",
        ]

        for pattern in non_gatt_patterns:
            if pattern in source_lower:
                LOGGER.debug(
                    "Source '%s' is not GATT-capable (passive scanner)", source
                )
                return False

        # ESPHome proxies with "btproxy" in name are GATT-capable
        if "btproxy" in source_lower or "proxy" in source_lower:
            LOGGER.debug("Source '%s' is GATT-capable (BT Proxy)", source)
            return True

        # Local adapters are always GATT-capable
        if (
            source_lower.startswith("hci")
            or "bcm" in source_lower
            or "brcm" in source_lower
        ):
            LOGGER.debug("Source '%s' is GATT-capable (local adapter)", source)
            return True

        # Default: assume capable (might be a renamed proxy or other adapter)
        LOGGER.debug("Source '%s' assumed GATT-capable (unknown type)", source)
        return True

    def _is_adapter_in_cooldown(self, source: str) -> bool:
        """Check if an adapter is in failure cooldown.

        Args:
            source: The Bluetooth source identifier

        Returns:
            True if the adapter recently failed and should be skipped
        """
        fail_time = self._adapter_failures.get(source)
        if fail_time is None:
            return False

        elapsed = time.time() - fail_time
        if elapsed < ADAPTER_FAILURE_COOLDOWN:
            LOGGER.debug(
                "Adapter '%s' in cooldown (%.0fs remaining)",
                source,
                ADAPTER_FAILURE_COOLDOWN - elapsed,
            )
            return True

        # Cooldown expired, remove from failures
        del self._adapter_failures[source]
        LOGGER.debug("Adapter '%s' cooldown expired, now available", source)
        return False

    def _mark_adapter_failed(self, source: str) -> None:
        """Mark an adapter as failed, putting it in cooldown.

        Args:
            source: The Bluetooth source identifier that failed
        """
        self._adapter_failures[source] = time.time()
        LOGGER.debug(
            "Marked adapter '%s' as failed (cooldown: %.0fs)",
            source,
            ADAPTER_FAILURE_COOLDOWN,
        )

    def _clear_adapter_failure(self, source: str) -> None:
        """Clear adapter failure status after successful connection.

        Args:
            source: The Bluetooth source identifier
        """
        if source in self._adapter_failures:
            del self._adapter_failures[source]
            LOGGER.debug("Cleared failure status for adapter '%s'", source)

    def _get_gatt_capable_device(self) -> BLEDevice | None:
        """Get a BLE device from a GATT-capable adapter.

        This method filters out passive-only Bluetooth sources (like Shelly plugs)
        and prefers GATT-capable adapters (ESPHome Proxies, local adapters).

        Adapters that recently failed are put in a cooldown period and will be
        skipped in favor of other available adapters.

        Returns:
            BLEDevice from a GATT-capable source, or None if not found
        """
        if not self._hass:
            return self._ble_device

        # Get all service infos for this device from all adapters
        # We need to find one from a GATT-capable source
        all_service_infos = bluetooth.async_scanner_devices_by_address(
            self._hass, self._mac, connectable=True
        )

        gatt_capable_infos = []
        cooldown_infos = []
        non_gatt_infos = []

        for scanner_device in all_service_infos:
            source = scanner_device.scanner.source
            if not self._is_gatt_capable_source(source):
                non_gatt_infos.append((scanner_device, source))
            elif self._is_adapter_in_cooldown(source):
                cooldown_infos.append((scanner_device, source))
            else:
                gatt_capable_infos.append((scanner_device, source))

        if gatt_capable_infos:
            # Pick the one with best RSSI from available GATT-capable sources
            best = max(
                gatt_capable_infos, key=lambda x: x[0].advertisement.rssi or -100
            )
            LOGGER.info(
                "Selected GATT-capable adapter '%s' for %s (RSSI: %s, skipped %d non-GATT, %d in cooldown)",
                best[1],
                self._mac,
                best[0].advertisement.rssi,
                len(non_gatt_infos),
                len(cooldown_infos),
            )
            return best[0].ble_device

        # If all GATT-capable adapters are in cooldown, use one anyway (best effort)
        if cooldown_infos:
            best = max(cooldown_infos, key=lambda x: x[0].advertisement.rssi or -100)
            LOGGER.warning(
                "All GATT-capable adapters in cooldown for %s, using '%s' anyway (RSSI: %s)",
                self._mac,
                best[1],
                best[0].advertisement.rssi,
            )
            return best[0].ble_device

        if non_gatt_infos:
            LOGGER.warning(
                "No GATT-capable adapters found for %s! "
                "Only passive scanners available: %s. "
                "Consider adding an ESPHome Bluetooth Proxy with 'active: true'.",
                self._mac,
                [src for _, src in non_gatt_infos],
            )

        # Fallback to HA's default selection
        return bluetooth.async_ble_device_from_address(
            self._hass, self._mac, connectable=True
        )

    def _select_best_adapter(self) -> None:
        """Select the best GATT-capable adapter for the device."""
        if not self._hass:
            return

        fresh_device = self._get_gatt_capable_device()
        if fresh_device:
            self._ble_device = fresh_device
            service_info = bluetooth.async_last_service_info(
                self._hass, self._mac, connectable=True
            )
            if service_info and service_info.rssi:
                self.update_rssi(service_info.rssi)
            LOGGER.info(
                "Selected adapter for %s (name: %s, RSSI: %s dBm)",
                self._mac,
                getattr(fresh_device, "name", "unknown"),
                service_info.rssi if service_info else "unknown",
            )
            return

        # Try non-connectable as fallback
        fresh_device = bluetooth.async_ble_device_from_address(
            self._hass, self._mac, connectable=False
        )
        if fresh_device:
            LOGGER.debug(
                "Device %s only available as non-connectable, trying anyway",
                self._mac,
            )
            self._ble_device = fresh_device
        else:
            LOGGER.debug(
                "Device %s not found by HA, using cached reference",
                self._mac,
            )

    async def _setup_after_connect(self) -> bool:
        """Set up characteristics, notifications, and initial state after GATT connect.

        Returns:
            True if setup succeeded, False if characteristics not found.
        """
        if self._client is None:
            return False

        # Find characteristics
        self._write_uuid = None
        self._read_uuid = None
        for service in self._client.services:
            for char in service.characteristics:
                if char.uuid == WRITE_CHARACTERISTIC_UUID:
                    self._write_uuid = char.uuid
                if char.uuid == READ_CHARACTERISTIC_UUID:
                    self._read_uuid = char.uuid

        if not self._read_uuid or not self._write_uuid:
            LOGGER.error(
                "Required characteristics not found on %s (read: %s, write: %s)",
                self._mac,
                self._read_uuid,
                self._write_uuid,
            )
            await self.disconnect()
            return False

        # Start notifications (with bleak 2.0.0 workaround)
        try:
            await self._client.start_notify(
                self._read_uuid,
                self._handle_notification,
                bluez={"use_start_notify": True},
            )
        except TypeError:
            await self._client.start_notify(self._read_uuid, self._handle_notification)

        # Initial device setup sequence
        await self._send_packet([CMD_DEVICE_PERMISSION])
        await asyncio.sleep(STATUS_DELAY)
        await self._request_status()
        await asyncio.sleep(STATUS_DELAY)
        await self.sync_time()

        if self._feedback_enabled is None:
            await asyncio.sleep(STATUS_DELAY)
            await self._send_packet([CMD_SETTINGS_READ])

        if self._wl90 is not None:
            await self._query_wl90_state()

        if not self._available:
            self._available = True
            await self._trigger_update()

        return True

    async def _query_wl90_state(self) -> None:
        """Query WL90-specific state (alarms, radio, music)."""
        await asyncio.sleep(STATUS_DELAY)
        for slot_byte in (0x01, 0x07, 0x03):
            await self._send_packet([CMD_ALARM_SYNC, slot_byte])
            await asyncio.sleep(STATUS_DELAY)
        await self._send_packet([CMD_RADIO_SYNC_STATUS])
        await asyncio.sleep(STATUS_DELAY)
        await self._send_packet([CMD_MUSIC_QUERY])

    async def connect(self) -> bool:
        """Connect to the device using Home Assistant's Bluetooth stack.

        Preferentially selects GATT-capable adapters (ESPHome Proxies,
        local Bluetooth) over passive-only scanners (Shelly devices).
        """
        try:
            if self._client is not None and self._client.is_connected:
                LOGGER.debug("Already connected to %s", self._mac)
                return True

            LOGGER.info(
                "Connecting to %s (device: %s, RSSI: %s dBm)",
                self._mac,
                getattr(self._ble_device, "name", "Unknown")
                if self._ble_device
                else "None",
                self._rssi or "unknown",
            )
            _connect_start = time.time()
            self._select_best_adapter()

            def get_fresh_device() -> BLEDevice:
                """Get fresh device from HA on each retry."""
                if self._hass:
                    fresh = self._get_gatt_capable_device()
                    if fresh:
                        old_name = getattr(self._ble_device, "name", "?")
                        new_name = getattr(fresh, "name", "?")
                        if old_name != new_name:
                            LOGGER.debug(
                                "Switched adapter: %s -> %s", old_name, new_name
                            )
                        self._ble_device = fresh
                        return fresh
                return self._ble_device

            self._client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self._mac,
                disconnected_callback=self._on_disconnect,
                max_attempts=5,
                ble_device_callback=get_fresh_device,
            )

            LOGGER.info(
                "Connected to %s successfully in %.1fs (RSSI: %s dBm)",
                self._mac,
                time.time() - _connect_start,
                self._rssi or "unknown",
            )

            if not await self._setup_after_connect():
                return False

            # Connection successful - clear adapter failure and track metrics
            if self._hass:
                service_info = bluetooth.async_last_service_info(
                    self._hass, self._mac, connectable=True
                )
                if service_info:
                    self._clear_adapter_failure(service_info.source)

            self._reconnect_backoff = RECONNECT_INITIAL_BACKOFF
            self._ever_connected = True
            if self._connection_start_time is not None:
                self._reconnect_count += 1
            self._connection_start_time = time.time()
            self._start_watchdog()
        except (
            BleakError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
            AttributeError,
        ) as err:
            LOGGER.error(
                "Error connecting to %s: %s (type: %s)",
                self._mac,
                err,
                type(err).__name__,
            )
        else:
            return True

        # Mark the adapter that failed so we try a different one next time
        if self._hass:
            service_info = bluetooth.async_last_service_info(
                self._hass, self._mac, connectable=True
            )
            if service_info:
                self._mark_adapter_failed(service_info.source)

        await self.disconnect()
        return False

    async def update(self) -> None:
        """Update device state by requesting current status."""
        LOGGER.debug("Update called for %s", self._mac)
        try:
            if (
                not self._client or not self._client.is_connected
            ) and not await self.connect():
                LOGGER.warning("Could not connect to %s for update", self._mac)
                return

            await self._request_status()
        except BleakError as err:
            LOGGER.error("BleakError during update for %s: %s", self._mac, err)
            await self.disconnect()
        except TimeoutError as err:
            LOGGER.error("Timeout during update for %s: %s", self._mac, err)
            await self.disconnect()
        except OSError as err:
            LOGGER.error("OS error during update for %s: %s", self._mac, err)
            await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect from the device and reset connection state."""
        LOGGER.debug("Disconnecting from %s", self._mac)

        # Stop the connection watchdog
        self._stop_watchdog()

        if self._client is not None and self._client.is_connected:
            try:
                if self._read_uuid:
                    await self._client.stop_notify(self._read_uuid)
            except BleakError as err:
                LOGGER.debug("BleakError stopping notifications: %s", err)
            except TimeoutError as err:
                LOGGER.debug("Timeout stopping notifications: %s", err)
            except OSError as err:
                LOGGER.debug("OS error stopping notifications: %s", err)

            try:
                await self._client.disconnect()
                LOGGER.info("Disconnected from %s", self._mac)
            except BleakError as err:
                LOGGER.debug("BleakError during disconnect: %s", err)
            except TimeoutError as err:
                LOGGER.debug("Timeout during disconnect: %s", err)
            except OSError as err:
                LOGGER.debug("OS error during disconnect: %s", err)

        self._available = False
        self._light_on = False
        self._color_on = False
