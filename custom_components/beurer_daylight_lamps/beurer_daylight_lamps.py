"""Beurer Daylight Lamp BLE communication module."""
from __future__ import annotations

import asyncio
from collections.abc import Callable

from bleak import BleakClient, BleakError, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
from homeassistant.components.light import ColorMode

from .const import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DEVICE_NAME_PREFIXES,
    LOGGER,
    MODE_RGB,
    MODE_WHITE,
    READ_CHARACTERISTIC_UUID,
    SUPPORTED_EFFECTS,
    WRITE_CHARACTERISTIC_UUID,
)


async def discover() -> list[BLEDevice]:
    """Discover Beurer daylight lamps via BLE scan."""
    devices = await BleakScanner.discover(timeout=DEFAULT_SCAN_TIMEOUT)
    LOGGER.debug(
        "Discovered %d BLE devices",
        len(devices),
    )

    beurer_devices: list[BLEDevice] = []
    for device in devices:
        if device.name and device.name.lower().startswith(DEVICE_NAME_PREFIXES):
            beurer_devices.append(device)
            LOGGER.debug(
                "Found Beurer device: %s - %s",
                device.address,
                device.name,
            )

    # Fallback: check for devices with matching characteristics
    if not beurer_devices:
        LOGGER.debug("No devices found by name, checking characteristics...")
        for device in devices:
            if await _has_beurer_characteristics(device):
                beurer_devices.append(device)
                LOGGER.debug(
                    "Found device by characteristics: %s - %s",
                    device.address,
                    device.name,
                )

    return beurer_devices


async def _has_beurer_characteristics(device: BLEDevice) -> bool:
    """Check if device has Beurer BLE characteristics."""
    try:
        async with BleakClient(device, timeout=10.0) as client:
            if not client.is_connected:
                return False
            has_read = any(
                char.uuid == READ_CHARACTERISTIC_UUID
                for service in client.services
                for char in service.characteristics
            )
            has_write = any(
                char.uuid == WRITE_CHARACTERISTIC_UUID
                for service in client.services
                for char in service.characteristics
            )
            return has_read and has_write
    except (BleakError, TimeoutError, OSError):
        return False


async def get_device(mac: str) -> BLEDevice | None:
    """Get BLE device by MAC address."""
    # Try direct lookup first
    try:
        device = await BleakScanner.find_device_by_address(
            mac, timeout=DEFAULT_SCAN_TIMEOUT
        )
        if device:
            LOGGER.debug("Found device by MAC: %s - %s", device.address, device.name)
            return device
    except BleakError as err:
        LOGGER.debug("BleakError finding device %s: %s", mac, err)
    except Exception as err:
        LOGGER.debug("Error finding device %s: %s", mac, err)

    # Fallback to full scan
    LOGGER.debug("Performing full scan for MAC: %s", mac)
    try:
        devices = await BleakScanner.discover(timeout=DEFAULT_SCAN_TIMEOUT)
        for device in devices:
            if device.address.lower() == mac.lower():
                return device
    except Exception as err:
        LOGGER.error("Error during device discovery for %s: %s", mac, err)

    return None


class BeurerInstance:
    """Representation of a Beurer daylight lamp BLE device."""

    def __init__(self, device: BLEDevice) -> None:
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

        self._update_callback: Callable[[], None] | None = None
        self._is_on: bool | None = None
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

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection callback."""
        LOGGER.debug("Disconnected from %s", self._mac)
        self._is_on = None
        self._light_on = False
        self._color_on = False
        self._write_uuid = None
        self._read_uuid = None
        if self._update_callback:
            asyncio.create_task(self._trigger_update())

    def set_update_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for state updates."""
        self._update_callback = callback

    @property
    def mac(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    def is_on(self) -> bool | None:
        """Return True if lamp is on."""
        return self._is_on

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

    @property
    def supported_effects(self) -> list[str]:
        """Return list of supported effects."""
        return self._supported_effects

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
        """Write data to the device."""
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
        except Exception as err:
            LOGGER.error("Error during write to %s: %s", self._mac, err)
            await self.disconnect()
            return False

    async def _send_packet(self, message: list[int]) -> bool:
        """Send a command packet to the device."""
        if not self._client.is_connected:
            if not await self.connect():
                return False

        length = len(message)
        checksum = self._calculate_checksum(length + 2, message)
        packet = bytearray(
            [0xFE, 0xEF, 0x0A, length + 7, 0xAB, 0xAA, length + 2]
            + message
            + [checksum, 0x55, 0x0D, 0x0A]
        )
        return await self._write(packet)

    async def set_color(
        self, rgb: tuple[int, int, int], _from_turn_on: bool = False
    ) -> None:
        """Set RGB color."""
        r, g, b = rgb
        LOGGER.debug("Setting color R=%d, G=%d, B=%d for %s", r, g, b, self._mac)

        self._mode = ColorMode.RGB
        self._rgb_color = rgb

        if not self._color_on:
            LOGGER.debug("Activating RGB mode")
            await self._send_packet([0x37, MODE_RGB])
            await asyncio.sleep(0.3)
            self._color_on = True
            self._light_on = False
            self._is_on = True
            self._effect = "Off"
            await self._send_packet([0x34, 0])
            await asyncio.sleep(0.3)

        await self._send_packet([0x32, r, g, b])
        await asyncio.sleep(0.3)
        await self._request_status()

    async def set_color_brightness(
        self, brightness: int | None, _from_turn_on: bool = False
    ) -> None:
        """Set color mode brightness (0-255)."""
        if brightness is None:
            brightness = 255

        LOGGER.debug("Setting color brightness to %d for %s", brightness, self._mac)
        self._mode = ColorMode.RGB
        self._color_brightness = brightness

        if not _from_turn_on and (not self._is_on or not self._color_on):
            await self.turn_on()
            return

        brightness_percent = max(0, min(100, int(brightness / 255 * 100)))
        await self._send_packet([0x31, MODE_RGB, brightness_percent])
        await asyncio.sleep(0.5)
        await self._request_status()

    async def set_white(
        self, intensity: int | None, _from_turn_on: bool = False
    ) -> None:
        """Set white light intensity (0-255)."""
        if intensity is None:
            intensity = 255

        LOGGER.debug("Setting white intensity to %d for %s", intensity, self._mac)
        self._mode = ColorMode.WHITE
        self._brightness = intensity

        if not self._light_on:
            LOGGER.debug("Activating white mode")
            await self._send_packet([0x37, MODE_WHITE])
            await asyncio.sleep(0.3)
            self._light_on = True
            self._color_on = False
            self._is_on = True

        intensity_percent = max(0, min(100, int(intensity / 255 * 100)))
        await self._send_packet([0x31, MODE_WHITE, intensity_percent])
        await asyncio.sleep(0.3)
        await self._request_status()

    async def set_effect(self, effect: str | None, _from_turn_on: bool = False) -> None:
        """Set light effect."""
        if effect is None:
            effect = "Off"

        LOGGER.debug("Setting effect to '%s' for %s", effect, self._mac)
        self._mode = ColorMode.RGB
        self._effect = effect

        if not _from_turn_on and (not self._is_on or not self._color_on):
            await self.turn_on()
            return

        await self._send_packet([0x34, self._find_effect_index(effect)])
        await asyncio.sleep(0.5)
        await self._request_status()

    async def turn_on(self) -> None:
        """Turn on the lamp."""
        LOGGER.debug(
            "Turning on %s (mode=%s, is_on=%s)",
            self._mac,
            self._mode,
            self._is_on,
        )

        if not self._client.is_connected:
            if not await self.connect():
                LOGGER.error("Failed to connect for turn_on")
                return

        if self._mode == ColorMode.WHITE:
            await self._send_packet([0x37, MODE_WHITE])
            await asyncio.sleep(0.5)
            self._light_on = True
            self._color_on = False
        else:
            await self._send_packet([0x37, MODE_RGB])
            await asyncio.sleep(0.5)
            self._color_on = True
            self._light_on = False

            if not self._is_on:
                await asyncio.sleep(0.5)
                await self.set_effect(self._effect or "Off", _from_turn_on=True)
                await asyncio.sleep(0.5)
                if self._rgb_color != (0, 0, 0):
                    await self.set_color(self._rgb_color, _from_turn_on=True)
                await asyncio.sleep(0.5)
                if self._color_brightness:
                    await self.set_color_brightness(
                        self._color_brightness, _from_turn_on=True
                    )

        self._is_on = True
        await asyncio.sleep(0.5)
        await self._request_status()

    async def turn_off(self) -> None:
        """Turn off the lamp."""
        LOGGER.debug("Turning off %s", self._mac)
        await self._send_packet([0x35, MODE_WHITE])
        await asyncio.sleep(0.1)
        await self._send_packet([0x35, MODE_RGB])
        self._is_on = False
        self._light_on = False
        self._color_on = False
        await asyncio.sleep(0.15)
        await self._request_status()

    async def _request_status(self) -> None:
        """Request status update from device."""
        LOGGER.debug("Requesting status from %s", self._mac)
        await self._send_packet([0x30, MODE_WHITE])
        await asyncio.sleep(0.2)
        await self._send_packet([0x30, MODE_RGB])

    async def _trigger_update(self) -> None:
        """Trigger Home Assistant state update."""
        if self._update_callback:
            LOGGER.debug("Triggering HA update for %s", self._mac)
            self._update_callback()

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
            if self._is_on or self._light_on or self._color_on:
                trigger_update = True
            self._is_on = False
            self._light_on = False
            self._color_on = False
            LOGGER.debug("Device off notification")

        elif version == 0:  # Shutdown
            LOGGER.debug("Device shutting down")
            await self.disconnect()
            return

        new_is_on = self._light_on or self._color_on
        if self._is_on != new_is_on:
            trigger_update = True
        self._is_on = new_is_on

        if trigger_update:
            await self._trigger_update()

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            if self._client.is_connected:
                return True

            LOGGER.debug("Connecting to %s", self._mac)

            # Recreate client if needed
            if not self._client:
                self._client = BleakClient(
                    self._ble_device, disconnected_callback=self._on_disconnect
                )

            await self._client.connect(timeout=DEFAULT_CONNECT_TIMEOUT)
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
        except TimeoutError:
            LOGGER.error("Timeout connecting to %s", self._mac)
        except Exception as err:
            LOGGER.error("Error connecting to %s: %s", self._mac, err)

        await self.disconnect()
        return False

    async def update(self) -> None:
        """Update device state."""
        LOGGER.debug("Update called for %s", self._mac)
        try:
            if not self._client.is_connected:
                if not await self.connect():
                    LOGGER.warning("Could not connect to %s for update", self._mac)
                    return

            await self._request_status()
        except Exception as err:
            LOGGER.error("Error during update for %s: %s", self._mac, err)
            await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        LOGGER.debug("Disconnecting from %s", self._mac)

        if self._client and self._client.is_connected:
            try:
                if self._read_uuid:
                    await self._client.stop_notify(self._read_uuid)
            except BleakError as err:
                LOGGER.debug("Error stopping notifications: %s", err)
            except Exception as err:
                LOGGER.debug("Error during notification stop: %s", err)

            try:
                await self._client.disconnect()
                LOGGER.info("Disconnected from %s", self._mac)
            except Exception as err:
                LOGGER.debug("Error during disconnect: %s", err)

        self._is_on = None
        self._light_on = False
        self._color_on = False
