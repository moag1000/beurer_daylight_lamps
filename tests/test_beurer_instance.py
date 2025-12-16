"""Test Beurer BLE communication module."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode


class TestBeurerInstance:
    """Tests for BeurerInstance class."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        device.rssi = -60
        return device

    @pytest.fixture
    def mock_client(self):
        """Create a mock BleakClient."""
        client = MagicMock()
        client.is_connected = False
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.write_gatt_char = AsyncMock()
        client.start_notify = AsyncMock()
        client.stop_notify = AsyncMock()
        client.services = []
        return client

    def test_init_valid_device(self, mock_device):
        """Test initialization with valid device."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device, rssi=-60)

        assert instance.mac == "AA:BB:CC:DD:EE:FF"
        assert instance.rssi == -60
        assert instance.is_on is None  # Not available yet
        assert instance._available is False
        assert instance.color_mode == ColorMode.WHITE
        assert instance.effect == "Off"

    def test_init_none_device_raises(self):
        """Test initialization with None device raises ValueError."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        with pytest.raises(ValueError, match="Cannot initialize BeurerInstance with None"):
            BeurerInstance(None)

    def test_init_invalid_device_raises(self):
        """Test initialization with invalid device raises ValueError."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        invalid_device = MagicMock(spec=[])  # No 'address' attribute
        with pytest.raises(ValueError, match="Invalid device object"):
            BeurerInstance(invalid_device)

    def test_set_color_mode(self, mock_device):
        """Test set_color_mode public method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.color_mode == ColorMode.WHITE

        instance.set_color_mode(ColorMode.RGB)
        assert instance.color_mode == ColorMode.RGB

        instance.set_color_mode(ColorMode.WHITE)
        assert instance.color_mode == ColorMode.WHITE

    def test_update_rssi(self, mock_device):
        """Test RSSI update method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device, rssi=-60)
        assert instance.rssi == -60

        instance.update_rssi(-50)
        assert instance.rssi == -50

        # None should not update
        instance.update_rssi(None)
        assert instance.rssi == -50

        # Same value should not trigger (no side effects to verify, but no error)
        instance.update_rssi(-50)
        assert instance.rssi == -50

    def test_public_properties(self, mock_device):
        """Test public properties for diagnostics."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device, rssi=-60)

        # Initially not connected
        assert instance.is_connected is False
        assert instance.write_uuid is None
        assert instance.read_uuid is None

    def test_callback_management(self, mock_device):
        """Test callback registration and removal."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        callback1 = MagicMock()
        callback2 = MagicMock()

        # Add callbacks
        instance.set_update_callback(callback1)
        instance.set_update_callback(callback2)
        assert len(instance._update_callbacks) == 2

        # Adding same callback again should not duplicate
        instance.set_update_callback(callback1)
        assert len(instance._update_callbacks) == 2

        # None should be ignored
        instance.set_update_callback(None)
        assert len(instance._update_callbacks) == 2

        # Remove callback
        instance.remove_update_callback(callback1)
        assert len(instance._update_callbacks) == 1
        assert callback2 in instance._update_callbacks

        # Remove non-existent callback should not error
        instance.remove_update_callback(callback1)
        assert len(instance._update_callbacks) == 1

    def test_find_effect_index(self, mock_device):
        """Test effect index lookup."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        assert instance._find_effect_index("Off") == 0
        assert instance._find_effect_index("Rainbow") == 2
        assert instance._find_effect_index("Summer") == 10
        assert instance._find_effect_index(None) == 0
        assert instance._find_effect_index("NonExistent") == 0  # Defaults to Off

    def test_calculate_checksum(self, mock_device):
        """Test checksum calculation."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        # Checksum is XOR of length and all data bytes
        result = instance._calculate_checksum(5, [0x30, 0x01])
        expected = 5 ^ 0x30 ^ 0x01
        assert result == expected


class TestNotificationParsing:
    """Tests for BLE notification parsing."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_short_notification_ignored(self, mock_device):
        """Test that short notifications are ignored."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # Short data (less than 10 bytes)
        short_data = bytearray([0x00] * 5)
        await instance._handle_notification(char, short_data)

        # Should not crash, state unchanged (still unavailable)
        assert instance.is_on is None
        assert instance._available is False

    @pytest.mark.asyncio
    async def test_white_mode_notification(self, mock_device):
        """Test parsing white mode status notification."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # White mode notification: version=1, on=1, brightness=50%
        data = bytearray([0x00] * 11)
        data[8] = 1  # version = white mode
        data[9] = 1  # on
        data[10] = 50  # brightness 50%

        await instance._handle_notification(char, data)

        assert instance._available is True  # Now available after notification
        assert instance._light_on is True
        assert instance.is_on is True  # Derived from _light_on
        assert instance._brightness == 127  # 50% of 255
        assert instance.color_mode == ColorMode.WHITE

    @pytest.mark.asyncio
    async def test_rgb_mode_notification(self, mock_device):
        """Test parsing RGB mode status notification."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # RGB mode notification: version=2, on=1, brightness=100%, rgb=(255,128,64), effect=2
        data = bytearray([0x00] * 17)
        data[8] = 2  # version = RGB mode
        data[9] = 1  # on
        data[10] = 100  # brightness 100%
        data[13] = 255  # R
        data[14] = 128  # G
        data[15] = 64   # B
        data[16] = 2    # effect index (Rainbow)

        await instance._handle_notification(char, data)

        assert instance._available is True
        assert instance._color_on is True
        assert instance.is_on is True  # Derived from _color_on
        assert instance._color_brightness == 255
        assert instance._rgb_color == (255, 128, 64)
        assert instance._effect == "Rainbow"
        assert instance.color_mode == ColorMode.RGB

    @pytest.mark.asyncio
    async def test_device_off_notification(self, mock_device):
        """Test parsing device off notification."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = True
        instance._light_on = True
        char = MagicMock()

        # Device off notification: version=255
        data = bytearray([0x00] * 10)
        data[8] = 255  # version = device off

        await instance._handle_notification(char, data)

        assert instance._available is True  # Still available, just off
        assert instance.is_on is False  # Derived from _light_on and _color_on
        assert instance._light_on is False
        assert instance._color_on is False


class TestDiscovery:
    """Tests for device discovery functions."""

    @pytest.mark.asyncio
    async def test_get_device_direct_lookup(self):
        """Test get_device with direct MAC lookup."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            get_device,
        )

        mock_device = MagicMock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        mock_device.name = "TL100"
        mock_device.rssi = -60

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakScanner.find_device_by_address",
            new_callable=AsyncMock,
            return_value=mock_device,
        ):
            device, rssi = await get_device("AA:BB:CC:DD:EE:FF")

        assert device == mock_device
        assert rssi == -60

    @pytest.mark.asyncio
    async def test_get_device_not_found(self):
        """Test get_device when device is not found."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            get_device,
        )

        mock_scanner_instance = MagicMock()
        mock_scanner_instance.start = AsyncMock()
        mock_scanner_instance.stop = AsyncMock()

        # Create a mock class that returns our instance and has the class method
        mock_scanner_class = MagicMock(return_value=mock_scanner_instance)
        mock_scanner_class.find_device_by_address = AsyncMock(return_value=None)

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakScanner",
            mock_scanner_class,
        ), patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            device, rssi = await get_device("AA:BB:CC:DD:EE:FF")

        assert device is None
        assert rssi is None

    @pytest.mark.asyncio
    async def test_discover_by_name(self):
        """Test discover finds devices by name prefix."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            discover,
        )

        mock_device1 = MagicMock()
        mock_device1.address = "AA:BB:CC:DD:EE:FF"
        mock_device1.name = "TL100-1234"

        mock_device2 = MagicMock()
        mock_device2.address = "11:22:33:44:55:66"
        mock_device2.name = "Other Device"

        mock_device3 = MagicMock()
        mock_device3.address = "77:88:99:AA:BB:CC"
        mock_device3.name = "beurer-lamp"

        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakScanner.discover",
            new_callable=AsyncMock,
            return_value=[mock_device1, mock_device2, mock_device3],
        ):
            devices = await discover()

        assert len(devices) == 2
        assert mock_device1 in devices
        assert mock_device3 in devices
        assert mock_device2 not in devices
