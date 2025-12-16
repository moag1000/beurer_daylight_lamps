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
import logging
import time
from collections.abc import Callable

from bleak import BleakClient, BleakError, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import establish_connection
from homeassistant.components.light import ColorMode
from homeassistant.helpers.device_registry import format_mac

from .const import (
    DEFAULT_SCAN_TIMEOUT,
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
    # Timing constants
    COMMAND_DELAY,
    MODE_CHANGE_DELAY,
    EFFECT_DELAY,
    STATUS_DELAY,
    TURN_OFF_DELAY,
    MIN_COMMAND_INTERVAL,
)


async def get_device(mac: str) -> tuple[BLEDevice | None, int | None]:
    """Get BLE device by MAC address.

    Args:
        mac: MAC address of the device to find

    Returns:
        Tuple of (device, rssi) or (None, None) if not found.
    """
    # Normalize MAC address for consistent comparison
    normalized_mac = format_mac(mac).upper()
    rssi = None

    # Try direct lookup first
    try:
        device = await BleakScanner.find_device_by_address(
            mac, timeout=DEFAULT_SCAN_TIMEOUT
        )
        if device:
            LOGGER.debug("Found device by MAC: %s - %s", device.address, device.name)
            # Try to get RSSI from advertisement data
            if hasattr(device, "rssi"):
                rssi = device.rssi
            return device, rssi
    except BleakError as err:
        LOGGER.debug("BleakError finding device %s: %s", mac, err)
    except (TimeoutError, asyncio.TimeoutError) as err:
        LOGGER.debug("Timeout finding device %s: %s", mac, err)
    except OSError as err:
        LOGGER.debug("OS error finding device %s: %s", mac, err)

    # Fallback to full scan with RSSI
    LOGGER.debug("Performing full scan for MAC: %s", mac)
    try:
        discovered: dict[str, tuple[BLEDevice, int | None]] = {}

        def detection_callback(device: BLEDevice, adv_data) -> None:
            device_mac = format_mac(device.address).upper()
            if device_mac == normalized_mac:
                discovered[device.address] = (
                    device,
                    adv_data.rssi if adv_data else None,
                )

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(DEFAULT_SCAN_TIMEOUT)
        await scanner.stop()

        # Return first match (should only be one)
        if discovered:
            for dev, dev_rssi in discovered.values():
                return dev, dev_rssi

    except BleakError as err:
        LOGGER.error("BleakError during device discovery for %s: %s", mac, err)
    except (TimeoutError, asyncio.TimeoutError) as err:
        LOGGER.error("Timeout during device discovery for %s: %s", mac, err)
    except OSError as err:
        LOGGER.error("OS error during device discovery for %s: %s", mac, err)

    return None, None


class BeurerInstance:
    """Representation of a Beurer daylight lamp BLE device."""

    def __init__(self, device: BLEDevice, rssi: int | None = None) -> None:
        """Initialize the Beurer instance."""
        if device is None:
            raise ValueError("Cannot initialize BeurerInstance with None device")
        if not hasattr(device, "address"):
            raise ValueError(f"Invalid device object: {device}")

        self._mac: str = device.address
        self._ble_device: BLEDevice = device
        self._client: BleakClient = BleakClient(
            device, disconnected_callback=self._on_disconnect
        )

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

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection callback."""
        LOGGER.debug("Disconnected from %s", self._mac)
        self._available = False
        self._light_on = False
        self._color_on = False
        self._write_uuid = None
        self._read_uuid = None
        if self._update_callbacks:
            self._safe_create_task(self._trigger_update())

    def _safe_create_task(self, coro) -> None:
        """Create an asyncio task with error handling.

        This prevents unhandled exceptions in fire-and-forget tasks from
        being silently lost.
        """

        async def _wrapped():
            try:
                await coro
            except Exception as err:
                LOGGER.error("Error in background task for %s: %s", self._mac, err)

        try:
            asyncio.create_task(_wrapped())
        except RuntimeError:
            # No event loop running (e.g., during shutdown)
            LOGGER.debug("Could not create task - no event loop running")

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
        """Return True if device is available (we've received status from it)."""
        return self._available

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
            LOGGER.warning("Effect '%s' not found, defaulting to 'Off'", effect)
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
        if not self._client.is_connected:
            LOGGER.warning("Device not connected, attempting reconnect")
            if not await self.connect():
                LOGGER.error("Failed to reconnect for write")
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
            LOGGER.warning("BleakError during write to %s: %s", self._mac, err)
            await self.disconnect()
            return False
        except (TimeoutError, asyncio.TimeoutError) as err:
            LOGGER.warning("Timeout during write to %s: %s", self._mac, err)
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
        if not self._client.is_connected:
            if not await self.connect():
                return False

        # Rate limiting: ensure minimum interval between commands
        now = time.monotonic()
        elapsed = now - self._last_command_time
        if elapsed < MIN_COMMAND_INTERVAL:
            await asyncio.sleep(MIN_COMMAND_INTERVAL - elapsed)

        length = len(message)
        checksum = self._calculate_checksum(length + 2, message)
        packet = bytearray(
            [0xFE, 0xEF, 0x0A, length + 7, 0xAB, 0xAA, length + 2]
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
        r, g, b = rgb
        LOGGER.debug("Setting color R=%d, G=%d, B=%d for %s", r, g, b, self._mac)

        self._mode = ColorMode.RGB
        self._rgb_color = rgb

        if not self._color_on:
            LOGGER.debug("Activating RGB mode")
            await self._send_packet([CMD_MODE, MODE_RGB])
            await asyncio.sleep(COMMAND_DELAY)
            self._color_on = True
            self._light_on = False
            self._available = True
            self._effect = "Off"
            await self._send_packet([CMD_EFFECT, 0])
            await asyncio.sleep(COMMAND_DELAY)

        await self._send_packet([CMD_COLOR, r, g, b])
        await asyncio.sleep(COMMAND_DELAY)
        await self._request_status()

    async def set_color_brightness(
        self, brightness: int | None, _from_turn_on: bool = False
    ) -> None:
        """Set color mode brightness (0-255).

        Args:
            brightness: Brightness value (0-255), defaults to 255 if None
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        if brightness is None:
            brightness = 255

        LOGGER.debug("Setting color brightness to %d for %s", brightness, self._mac)
        self._mode = ColorMode.RGB
        self._color_brightness = brightness

        if not _from_turn_on and (not self.is_on or not self._color_on):
            await self.turn_on()
            return

        brightness_percent = max(0, min(100, int(brightness / 255 * 100)))
        await self._send_packet([CMD_BRIGHTNESS, MODE_RGB, brightness_percent])
        await asyncio.sleep(MODE_CHANGE_DELAY)
        await self._request_status()

    async def set_white(
        self, intensity: int | None, _from_turn_on: bool = False
    ) -> None:
        """Set white light intensity (0-255).

        Args:
            intensity: Intensity value (0-255), defaults to 255 if None
            _from_turn_on: Internal flag to prevent recursion during turn_on
        """
        if intensity is None:
            intensity = 255

        LOGGER.debug("Setting white intensity to %d for %s", intensity, self._mac)
        self._mode = ColorMode.WHITE
        self._brightness = intensity

        if not self._light_on:
            LOGGER.debug("Activating white mode")
            await self._send_packet([CMD_MODE, MODE_WHITE])
            await asyncio.sleep(COMMAND_DELAY)
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
        self._mode = ColorMode.RGB
        self._effect = effect

        if not _from_turn_on and (not self.is_on or not self._color_on):
            await self.turn_on()
            return

        await self._send_packet([CMD_EFFECT, self._find_effect_index(effect)])
        await asyncio.sleep(EFFECT_DELAY)
        await self._request_status()

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

        if not self._client.is_connected:
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
        LOGGER.debug(
            "Notification from %s: %s",
            self._mac,
            data.hex(),
        )

        if len(data) < 10:
            LOGGER.warning("Short notification (%d bytes), ignoring", len(data))
            return

        version = data[8]
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

        elif version == 255:  # Device off
            if self._light_on or self._color_on:
                trigger_update = True
            self._light_on = False
            self._color_on = False
            LOGGER.debug("Device off notification")

        elif version == 0:  # Shutdown
            LOGGER.debug("Device shutting down")
            await self.disconnect()
            return

        # Mark as available once we've received any valid status
        if not self._available:
            self._available = True
            trigger_update = True

        if trigger_update:
            await self._trigger_update()

    async def connect(self) -> bool:
        """Connect to the device using bleak-retry-connector for reliability."""
        try:
            if self._client and self._client.is_connected:
                return True

            LOGGER.debug("Connecting to %s", self._mac)

            # Try to get fresh device reference with updated RSSI
            try:
                fresh_device = await BleakScanner.find_device_by_address(
                    self._mac, timeout=5.0
                )
                if fresh_device:
                    self._ble_device = fresh_device
                    if hasattr(fresh_device, "rssi") and fresh_device.rssi:
                        self.update_rssi(fresh_device.rssi)
            except (BleakError, TimeoutError, asyncio.TimeoutError, OSError) as err:
                LOGGER.debug("Could not refresh device info: %s", err)

            # Use bleak-retry-connector for reliable connection establishment
            self._client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._mac,
                disconnected_callback=self._on_disconnect,
                max_attempts=3,
            )
            LOGGER.info("Connected to %s", self._mac)

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
                LOGGER.error("Required characteristics not found on %s", self._mac)
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
            return True

        except BleakError as err:
            LOGGER.error("BleakError connecting to %s: %s", self._mac, err)
        except (TimeoutError, asyncio.TimeoutError):
            LOGGER.error("Timeout connecting to %s", self._mac)
        except OSError as err:
            LOGGER.error("OS error connecting to %s: %s", self._mac, err)

        await self.disconnect()
        return False

    async def update(self) -> None:
        """Update device state by requesting current status."""
        LOGGER.debug("Update called for %s", self._mac)
        try:
            if not self._client.is_connected:
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
        """Disconnect from the device and reset state."""
        LOGGER.debug("Disconnecting from %s", self._mac)

        if self._client and self._client.is_connected:
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
