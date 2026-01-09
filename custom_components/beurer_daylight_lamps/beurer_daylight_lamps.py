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
import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
from homeassistant.components.light import ColorMode  # type: ignore[attr-defined]

from .therapy import SunriseSimulation, SunriseProfile, TherapyTracker

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    LOGGER,
    MODE_RGB,
    MODE_WHITE,
    READ_CHARACTERISTIC_UUID,
    SUPPORTED_EFFECTS,
    WRITE_CHARACTERISTIC_UUID,
    # Protocol commands
    CMD_STATUS,
    CMD_BRIGHTNESS,
    CMD_COLOR,
    CMD_EFFECT,
    CMD_OFF,
    CMD_MODE,
    CMD_TIMER_VALUE,
    CMD_TIMER_TOGGLE,
    CMD_TIMER_CANCEL,
    # Timing constants
    COMMAND_DELAY,
    MODE_CHANGE_DELAY,
    EFFECT_DELAY,
    STATUS_DELAY,
    TURN_OFF_DELAY,
    MIN_COMMAND_INTERVAL,
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
        # Don't create BleakClient here - we'll create it fresh in connect()
        # This allows us to use updated device references from better proxies
        self._client: BleakClient | None = None

        self._update_callbacks: list[Callable[[], None]] = []
        self._available: bool = False  # True once we've received status from device
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
        self._rssi: int | None = rssi
        self._last_command_time: float = 0.0  # For rate limiting
        self._last_seen: float = time.time()  # Track when device was last seen
        self._ble_available: bool = True  # Track if device is seen by any BLE adapter
        # Diagnostic: raw notification data for reverse engineering
        self._last_raw_notification: str | None = None
        self._last_unknown_notification: str | None = None
        self._last_notification_version: int | None = None
        self._heartbeat_count: int = 0  # Counter for ACK/heartbeat packets
        # Timer state tracking (discovered via reverse engineering)
        self._timer_active: bool = False
        self._timer_minutes: int | None = None

        # Reconnection state (prevents multiple parallel reconnect attempts)
        self._reconnecting: bool = False

        # Therapy tracking - sunrise/sunset simulation and exposure tracking
        self._sunrise_simulation: SunriseSimulation | None = None
        self._therapy_tracker: TherapyTracker = TherapyTracker()

        # Reference to adaptive lighting switch (set by switch entity)
        self.adaptive_lighting_switch: Any = None

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
            self._safe_create_task(self._trigger_update(), "beurer_ble_reachable_update")

        # Auto-reconnect if:
        # 1. Device was BLE unavailable and we're not connected, OR
        # 2. Device is BLE available but not connected (stale connection)
        # But not if already reconnecting
        should_reconnect = (
            not self._reconnecting
            and not self.is_connected
            and (was_ble_unavailable or not self._available)
        )

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
            LOGGER.debug("Device %s marked as unavailable (no BLE advertisements)", self._mac)
            self._ble_available = False
            self._available = False
            self._safe_create_task(self._trigger_update(), "beurer_unavailable_update")

    async def _auto_reconnect(self) -> None:
        """Automatically reconnect when device becomes available again."""
        if self._reconnecting:
            return  # Already reconnecting

        self._reconnecting = True
        try:
            # Small delay to let BLE stack settle
            await asyncio.sleep(1)

            if self._available:
                # Already available, no need to reconnect
                return

            LOGGER.info("Auto-reconnecting to %s", self._mac)
            connected = await self.connect()

            if connected:
                LOGGER.info("Auto-reconnect to %s successful", self._mac)
            else:
                LOGGER.debug("Auto-reconnect to %s failed, will retry on next advertisement", self._mac)

        except Exception as err:
            LOGGER.debug("Auto-reconnect to %s failed: %s", self._mac, err)
        finally:
            self._reconnecting = False

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

    # Therapy tracking properties
    @property
    def sunrise_simulation(self) -> SunriseSimulation:
        """Return the sunrise simulation controller."""
        if self._sunrise_simulation is None:
            self._sunrise_simulation = SunriseSimulation(self)
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
        """Set the daily therapy goal."""
        self._therapy_tracker.daily_goal_minutes = max(1, min(120, minutes))
        self._safe_create_task(self._trigger_update(), "beurer_therapy_goal_update")

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection callback."""
        LOGGER.info("Disconnected from %s - will attempt reconnect", self._mac)
        self._available = False
        self._light_on = False
        self._color_on = False
        self._write_uuid = None
        self._read_uuid = None
        if self._update_callbacks:
            self._safe_create_task(self._trigger_update(), "beurer_disconnect_update")
        # Trigger auto-reconnect after disconnect (if device is still BLE reachable)
        if self._ble_available and not self._reconnecting:
            LOGGER.info("Device %s still BLE reachable, scheduling reconnect", self._mac)
            self._safe_create_task(self._auto_reconnect(), "beurer_disconnect_reconnect")

    def _safe_create_task(
        self, coro: Coroutine[Any, Any, None], name: str | None = None
    ) -> None:
        """Create an asyncio task with error handling.

        This prevents unhandled exceptions in fire-and-forget tasks from
        being silently lost. Uses Home Assistant's task creation when available.

        Args:
            coro: The coroutine to run
            name: Optional name for the task (for debugging)
        """
        task_name = name or f"beurer_task_{self._mac}"

        async def _wrapped() -> None:
            try:
                await coro
            except Exception as err:
                LOGGER.error("Error in background task '%s' for %s: %s", task_name, self._mac, err)

        try:
            # Prefer Home Assistant's task creation if available
            if self._hass is not None:
                self._hass.async_create_background_task(
                    _wrapped(),
                    task_name,
                )
            else:
                # Fallback for standalone usage
                asyncio.create_task(_wrapped(), name=task_name)
        except RuntimeError:
            # No event loop running (e.g., during shutdown)
            LOGGER.debug("Could not create task '%s' - no event loop running", task_name)

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
        """Return True if device is available.

        Device is available if:
        - Connected via GATT (active connection), OR
        - Reachable via BLE AND we've received status
        """
        # If actively connected, device is definitely available
        if self.is_connected:
            return True
        # Otherwise, need both BLE reachability and status received
        return self.ble_available and self._available

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
            LOGGER.debug("Effect '%s' not in supported list, defaulting to 'Off'", effect)
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
                return False

        # Safety check after reconnect (for type checker)
        if self._client is None:
            return False

        if not self._write_uuid:
            LOGGER.error("Write UUID not available")
            return False

        try:
            LOGGER.debug(
                "Writing to %s: %s",
                self._mac,
                data.hex(),
            )
            await self._client.write_gatt_char(self._write_uuid, data)
            return True
        except BleakError as err:
            LOGGER.debug("BleakError during write to %s: %s", self._mac, err)
            await self.disconnect()
            return False
        except (TimeoutError, asyncio.TimeoutError) as err:
            LOGGER.debug("Timeout during write to %s: %s", self._mac, err)
            await self.disconnect()
            return False
        except OSError as err:
            LOGGER.error("OS error during write to %s: %s", self._mac, err)
            await self.disconnect()
            return False

    async def _send_packet(self, message: list[int]) -> bool:
        """Send a command packet to the device.

        Includes rate limiting to prevent overwhelming the device with
        rapid command sequences.

        Args:
            message: List of command bytes to send

        Returns:
            True if packet was sent successfully, False otherwise.
        """
        if not self._client or not self._client.is_connected:
            if not await self.connect():
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
            [0xFE, 0xEF, 0x0A, length + 7, 0xAB, 0xAA, plen]
            + message
            + [checksum, 0x55, 0x0D, 0x0A]
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
            r, g, b, brightness, self._mac
        )

        self._mode = ColorMode.RGB
        self._rgb_color = (r, g, b)

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

    async def set_color_brightness(
        self, brightness: int | float | None, _from_turn_on: bool = False
    ) -> None:
        """Set color mode brightness (0-255).

        Args:
            brightness: Brightness value (0-255), defaults to 255 if None
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        if brightness is None:
            brightness = 255
        else:
            brightness = int(brightness)  # Ensure integer for BLE protocol

        LOGGER.debug("Setting color brightness to %d for %s", brightness, self._mac)
        self._color_brightness = brightness

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

    async def set_white(
        self, intensity: int | float | None, _from_turn_on: bool = False
    ) -> None:
        """Set white light intensity (0-255).

        Args:
            intensity: Intensity value (0-255), defaults to 255 if None
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        if intensity is None:
            intensity = 255
        else:
            intensity = int(intensity)  # Ensure integer for BLE protocol

        LOGGER.debug("Setting white intensity to %d for %s", intensity, self._mac)
        self._mode = ColorMode.WHITE
        self._brightness = intensity

        # Switch to white mode if not already active
        if not self._light_on:
            LOGGER.debug("Activating white mode")
            await self._send_packet([CMD_MODE, MODE_WHITE])
            await asyncio.sleep(MODE_CHANGE_DELAY)
            self._light_on = True
            self._color_on = False
            self._available = True

        intensity_percent = max(0, min(100, int(intensity / 255 * 100)))
        await self._send_packet([CMD_BRIGHTNESS, MODE_WHITE, intensity_percent])
        await asyncio.sleep(COMMAND_DELAY)
        await self._request_status()

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
            minutes, self._mac, mode_byte, self._mode
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
            self._mac, mode_byte, self._mode
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

        if not self._client or not self._client.is_connected:
            if not await self.connect():
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

    async def _handle_notification(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle BLE notification from device."""
        hex_str = data.hex()
        LOGGER.debug(
            "Notification from %s: %s",
            self._mac,
            hex_str,
        )

        # Store raw notification for diagnostics (always)
        self._last_raw_notification = hex_str

        if len(data) < 10:
            LOGGER.debug("Short notification (%d bytes), ignoring", len(data))
            return

        # Check payload length (byte 6) to determine packet type
        # Full status packets have payload_len >= 0x08
        # Short ACK/heartbeat packets have payload_len 0x04 and should be ignored
        # for status updates (they report version 0xFF which would turn off the light)
        payload_len = data[6] if len(data) > 6 else 0
        if payload_len < 0x08:
            LOGGER.debug(
                "Short payload (%d bytes), likely ACK/heartbeat - not updating state",
                payload_len
            )
            # Use heartbeat to confirm device is still alive
            self._last_seen = time.time()
            self._heartbeat_count += 1
            # Mark as available since we're receiving communication from the device
            if not self._available:
                self._available = True
            # Trigger update to refresh heartbeat counter sensor
            await self._trigger_update()
            return

        version = data[8]
        self._last_notification_version = version
        trigger_update = False

        if version == 1:  # White mode status
            new_light_on = data[9] == 1
            new_brightness = int(data[10] * 255 / 100) if new_light_on else None

            if self._light_on != new_light_on or self._brightness != new_brightness:
                trigger_update = True

            self._light_on = new_light_on
            self._brightness = new_brightness
            if self._light_on:
                self._mode = ColorMode.WHITE

            LOGGER.debug(
                "White status: on=%s, brightness=%s",
                self._light_on,
                self._brightness,
            )

        elif version == 2:  # RGB mode status
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
                trigger_update = True

            self._color_on = new_color_on
            self._effect = new_effect
            self._color_brightness = new_color_brightness
            self._rgb_color = new_rgb
            if self._color_on:
                self._mode = ColorMode.RGB

            LOGGER.debug(
                "RGB status: on=%s, brightness=%s, rgb=%s, effect=%s",
                self._color_on,
                self._color_brightness,
                self._rgb_color,
                self._effect,
            )

            # Track therapy exposure based on current RGB state
            # Therapy-relevant light: cool white (high blue component) at high brightness
            if self._color_on and self._color_brightness is not None:
                # Estimate color temperature from RGB (simplified: higher blue = cooler)
                r, g, b = self._rgb_color
                # Cool light has roughly equal R/G and higher relative values
                # Therapy-relevant: bright, balanced white (R≈G≈B with high values)
                is_white_ish = abs(r - g) < 50 and abs(g - b) < 50 and min(r, g, b) > 150
                brightness_pct = int(self._color_brightness / 255 * 100)
                # Estimate kelvin (very rough): white-ish light with high brightness
                estimated_kelvin = 5300 if is_white_ish else 3000
                self._therapy_tracker.update_session(estimated_kelvin, brightness_pct)
                if is_white_ish and brightness_pct >= 80:
                    # Start new session if not tracking, or continue existing
                    if self._therapy_tracker._current_session is None:
                        self._therapy_tracker.start_session(estimated_kelvin, brightness_pct)
            elif not self._color_on:
                # End session when color mode turns off
                self._therapy_tracker.end_session()

        elif version == 255:  # Device off
            if self._light_on or self._color_on:
                trigger_update = True
                # End therapy session when light turns off
                self._therapy_tracker.end_session()
            self._light_on = False
            self._color_on = False
            LOGGER.debug("Device off notification")

        elif version == 0:  # Shutdown
            LOGGER.debug("Device shutting down")
            await self.disconnect()
            return

        else:
            # Unknown version - store for reverse engineering
            self._last_unknown_notification = hex_str
            LOGGER.warning(
                "Unknown notification version %d from %s: hex=%s len=%d "
                "bytes=[%s]",
                version, self._mac, hex_str, len(data),
                ", ".join(f"0x{b:02x}" for b in data)
            )
            # Still mark as available - device is communicating
            if not self._available:
                self._available = True
            trigger_update = True  # Update sensors to show new unknown data

        # Mark as available once we've received any valid status
        if not self._available:
            self._available = True
            trigger_update = True

        if trigger_update:
            await self._trigger_update()

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
                LOGGER.debug("Source '%s' is not GATT-capable (passive scanner)", source)
                return False

        # ESPHome proxies with "btproxy" in name are GATT-capable
        if "btproxy" in source_lower or "proxy" in source_lower:
            LOGGER.debug("Source '%s' is GATT-capable (BT Proxy)", source)
            return True

        # Local adapters are always GATT-capable
        if source_lower.startswith("hci") or "bcm" in source_lower or "brcm" in source_lower:
            LOGGER.debug("Source '%s' is GATT-capable (local adapter)", source)
            return True

        # Default: assume capable (might be a renamed proxy or other adapter)
        LOGGER.debug("Source '%s' assumed GATT-capable (unknown type)", source)
        return True

    def _get_gatt_capable_device(self) -> BLEDevice | None:
        """Get a BLE device from a GATT-capable adapter.

        This method filters out passive-only Bluetooth sources (like Shelly plugs)
        and prefers GATT-capable adapters (ESPHome Proxies, local adapters).

        Returns:
            BLEDevice from a GATT-capable source, or None if not found
        """
        if not self._hass:
            return self._ble_device

        from homeassistant.components import bluetooth

        # Get all service infos for this device from all adapters
        # We need to find one from a GATT-capable source
        all_service_infos = bluetooth.async_scanner_devices_by_address(
            self._hass, self._mac, connectable=True
        )

        gatt_capable_infos = []
        non_gatt_infos = []

        for scanner_device in all_service_infos:
            source = scanner_device.scanner.source
            if self._is_gatt_capable_source(source):
                gatt_capable_infos.append((scanner_device, source))
            else:
                non_gatt_infos.append((scanner_device, source))

        if gatt_capable_infos:
            # Pick the one with best RSSI from GATT-capable sources
            best = max(gatt_capable_infos, key=lambda x: x[0].advertisement.rssi or -100)
            LOGGER.info(
                "Selected GATT-capable adapter '%s' for %s (RSSI: %s, skipped %d non-GATT sources)",
                best[1],
                self._mac,
                best[0].advertisement.rssi,
                len(non_gatt_infos),
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

    async def connect(self) -> bool:
        """Connect to the device using Home Assistant's Bluetooth stack.

        This method preferentially selects GATT-capable adapters (ESPHome Proxies,
        local Bluetooth) over passive-only scanners (Shelly devices).

        Home Assistant automatically selects the best available adapter with
        free connection slots. We use ble_device_callback to get a fresh
        device reference on each retry attempt, allowing HA to pick a different
        adapter if the previous one failed (e.g., no slots available).
        """
        try:
            if self._client is not None and self._client.is_connected:
                LOGGER.debug("Already connected to %s", self._mac)
                return True

            LOGGER.info(
                "Connecting to %s (device: %s, RSSI: %s dBm)",
                self._mac,
                getattr(self._ble_device, "name", "Unknown") if self._ble_device else "None",
                self._rssi if self._rssi else "unknown",
            )
            _connect_start = time.time()

            # Get initial device from HA - prefer GATT-capable adapters
            if self._hass:
                from homeassistant.components import bluetooth

                # Try to get device from GATT-capable adapter first
                fresh_device = self._get_gatt_capable_device()

                if fresh_device:
                    self._ble_device = fresh_device
                    # Get RSSI from service info
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
                else:
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

            def get_fresh_device() -> BLEDevice:
                """Get fresh device from HA on each retry.

                This is the KEY for multi-adapter support: on each retry,
                we re-evaluate which GATT-capable adapter to use. If the previous
                adapter failed, we try the next GATT-capable one.
                """
                if self._hass:
                    # Use our GATT-capable filter instead of HA's default
                    fresh = self._get_gatt_capable_device()
                    if fresh:
                        old_name = getattr(self._ble_device, "name", "?")
                        new_name = getattr(fresh, "name", "?")
                        if old_name != new_name:
                            LOGGER.debug(
                                "Switched adapter: %s -> %s",
                                old_name,
                                new_name,
                            )
                        self._ble_device = fresh
                        return fresh
                return self._ble_device

            # Use establish_connection with ble_device_callback
            # On each retry, get_fresh_device selects the best GATT-capable adapter
            LOGGER.debug(
                "Establishing connection with bleak-retry-connector (max 5 attempts)..."
            )

            self._client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self._mac,
                disconnected_callback=self._on_disconnect,
                max_attempts=5,
                ble_device_callback=get_fresh_device,  # HA picks best adapter on each retry!
            )

            LOGGER.info(
                "Connected to %s successfully in %.1fs (RSSI: %s dBm)",
                self._mac,
                time.time() - _connect_start,
                self._rssi if self._rssi else "unknown",
            )

            # Connection successful - continue with setup

            # Find characteristics
            self._write_uuid = None
            self._read_uuid = None
            service_count = 0
            char_count = 0
            for service in self._client.services:
                service_count += 1
                for char in service.characteristics:
                    char_count += 1
                    if char.uuid == WRITE_CHARACTERISTIC_UUID:
                        self._write_uuid = char.uuid
                    if char.uuid == READ_CHARACTERISTIC_UUID:
                        self._read_uuid = char.uuid

            LOGGER.debug(
                "Discovered %d services with %d characteristics on %s",
                service_count,
                char_count,
                self._mac,
            )

            if not self._read_uuid or not self._write_uuid:
                LOGGER.error(
                    "Required characteristics not found on %s (read: %s, write: %s)",
                    self._mac,
                    self._read_uuid,
                    self._write_uuid,
                )
                await self.disconnect()
                return False

            LOGGER.debug(
                "Found characteristics - read: %s, write: %s",
                self._read_uuid,
                self._write_uuid,
            )

            # Start notifications
            await self._client.start_notify(self._read_uuid, self._handle_notification)
            LOGGER.debug("Notifications started for %s", self._mac)

            # Get initial status
            await self._request_status()

            # Mark as available - we have a working connection
            # (Don't wait for notification response, connection itself proves device is there)
            if not self._available:
                self._available = True
                await self._trigger_update()

            return True

        except BleakError as err:
            LOGGER.error(
                "BleakError connecting to %s: %s (type: %s)",
                self._mac,
                err,
                type(err).__name__,
            )
        except (TimeoutError, asyncio.TimeoutError) as err:
            LOGGER.error(
                "Timeout connecting to %s after all retry attempts: %s",
                self._mac,
                err,
            )
        except OSError as err:
            LOGGER.error(
                "OS error connecting to %s: %s (errno: %s)",
                self._mac,
                err,
                getattr(err, "errno", "N/A"),
            )
        except Exception as err:
            LOGGER.error(
                "Unexpected error connecting to %s: %s (type: %s)",
                self._mac,
                err,
                type(err).__name__,
            )

        await self.disconnect()
        return False

    async def update(self) -> None:
        """Update device state by requesting current status."""
        LOGGER.debug("Update called for %s", self._mac)
        try:
            if not self._client or not self._client.is_connected:
                if not await self.connect():
                    LOGGER.warning("Could not connect to %s for update", self._mac)
                    return

            await self._request_status()
        except BleakError as err:
            LOGGER.error("BleakError during update for %s: %s", self._mac, err)
            await self.disconnect()
        except (TimeoutError, asyncio.TimeoutError) as err:
            LOGGER.error("Timeout during update for %s: %s", self._mac, err)
            await self.disconnect()
        except OSError as err:
            LOGGER.error("OS error during update for %s: %s", self._mac, err)
            await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect from the device and reset connection state."""
        LOGGER.debug("Disconnecting from %s", self._mac)

        if self._client is not None and self._client.is_connected:
            try:
                if self._read_uuid:
                    await self._client.stop_notify(self._read_uuid)
            except BleakError as err:
                LOGGER.debug("BleakError stopping notifications: %s", err)
            except (TimeoutError, asyncio.TimeoutError) as err:
                LOGGER.debug("Timeout stopping notifications: %s", err)
            except OSError as err:
                LOGGER.debug("OS error stopping notifications: %s", err)

            try:
                await self._client.disconnect()
                LOGGER.info("Disconnected from %s", self._mac)
            except BleakError as err:
                LOGGER.debug("BleakError during disconnect: %s", err)
            except (TimeoutError, asyncio.TimeoutError) as err:
                LOGGER.debug("Timeout during disconnect: %s", err)
            except OSError as err:
                LOGGER.debug("OS error during disconnect: %s", err)

        self._available = False
        self._light_on = False
        self._color_on = False
