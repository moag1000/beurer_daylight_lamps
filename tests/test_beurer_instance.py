"""Test Beurer BLE communication module."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode


# Mock BleakClient before importing BeurerInstance to avoid platform-specific imports
@pytest.fixture(autouse=True)
def mock_bleak_client():
    """Mock BleakClient for all tests."""
    with patch(
        "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakClient"
    ) as mock:
        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.start_notify = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        mock_client.services = []
        mock.return_value = mock_client
        yield mock


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
        # Packet structure: [header...][len][magic][payload_len][payload...][checksum][trailer]
        # Byte 6 = payload_len: 0x08 for white status, 0x0C for RGB status
        data = bytearray([0x00] * 11)
        data[6] = 0x08  # payload_len = 0x08 (white status packet)
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
        # Byte 6 = payload_len: 0x0C for RGB status packet
        data = bytearray([0x00] * 17)
        data[6] = 0x0C  # payload_len = 0x0C (RGB status packet)
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
        # Byte 6 = payload_len: 0x08 for status packet (white mode structure)
        data = bytearray([0x00] * 10)
        data[6] = 0x08  # payload_len = 0x08 (status packet)
        data[8] = 255  # version = device off

        await instance._handle_notification(char, data)

        assert instance._available is True  # Still available, just off
        assert instance.is_on is False  # Derived from _light_on and _color_on
        assert instance._light_on is False
        assert instance._color_on is False


class TestBeurerInstanceWithHass:
    """Tests for BeurerInstance with Home Assistant integration."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_init_with_hass(self, mock_device):
        """Test initialization with hass reference."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        mock_hass = MagicMock()
        instance = BeurerInstance(mock_device, rssi=-60, hass=mock_hass)

        assert instance.mac == "AA:BB:CC:DD:EE:FF"
        assert instance.rssi == -60
        assert instance._hass == mock_hass

    def test_init_without_hass(self, mock_device):
        """Test initialization without hass (for testing/legacy)."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device, rssi=-60)

        assert instance.mac == "AA:BB:CC:DD:EE:FF"
        assert instance._hass is None


class TestBeurerDeviceAvailability:
    """Tests for BLE availability tracking."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_mark_seen_updates_timestamp(self, mock_device):
        """Test mark_seen updates last_seen timestamp."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        old_time = instance._last_seen

        import time
        time.sleep(0.01)
        instance.mark_seen()

        assert instance._last_seen > old_time

    def test_mark_seen_makes_available(self, mock_device):
        """Test mark_seen restores ble_available when previously unavailable."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._ble_available = False

        instance.mark_seen()

        assert instance._ble_available is True

    def test_mark_unavailable(self, mock_device):
        """Test mark_unavailable sets device as unavailable."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._ble_available = True
        instance._available = True

        instance.mark_unavailable()

        assert instance._ble_available is False
        assert instance._available is False

    def test_mark_unavailable_when_already_unavailable(self, mock_device):
        """Test mark_unavailable when already unavailable does nothing."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._ble_available = False

        # Should not crash
        instance.mark_unavailable()

        assert instance._ble_available is False

    def test_ble_available_property(self, mock_device):
        """Test ble_available property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.ble_available is True

        instance._ble_available = False
        assert instance.ble_available is False

    def test_last_seen_property(self, mock_device):
        """Test last_seen property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.last_seen > 0

    def test_available_property(self, mock_device):
        """Test available property combines ble_available and _available."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        # Initially not available (haven't received status)
        assert instance.available is False

        # Set both flags
        instance._ble_available = True
        instance._available = True
        assert instance.available is True

        # Only ble_available
        instance._available = False
        assert instance.available is False

        # Only _available
        instance._ble_available = False
        instance._available = True
        assert instance.available is False


class TestBeurerDeviceProperties:
    """Tests for additional device properties."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_is_on_when_unavailable(self, mock_device):
        """Test is_on returns None when device unavailable."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = False

        assert instance.is_on is None

    def test_is_on_when_light_on(self, mock_device):
        """Test is_on returns True when _light_on is True."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = True
        instance._light_on = True
        instance._color_on = False

        assert instance.is_on is True

    def test_is_on_when_color_on(self, mock_device):
        """Test is_on returns True when _color_on is True."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = True
        instance._light_on = False
        instance._color_on = True

        assert instance.is_on is True

    def test_is_on_when_both_off(self, mock_device):
        """Test is_on returns False when both modes are off."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = True
        instance._light_on = False
        instance._color_on = False

        assert instance.is_on is False

    def test_rgb_color_property(self, mock_device):
        """Test rgb_color property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.rgb_color == (255, 255, 255)

        instance._rgb_color = (100, 150, 200)
        assert instance.rgb_color == (100, 150, 200)

    def test_color_brightness_property(self, mock_device):
        """Test color_brightness property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.color_brightness is None

        instance._color_brightness = 200
        assert instance.color_brightness == 200

    def test_white_brightness_property(self, mock_device):
        """Test white_brightness property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.white_brightness is None

        instance._brightness = 150
        assert instance.white_brightness == 150

    def test_effect_property(self, mock_device):
        """Test effect property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.effect == "Off"

        instance._effect = "Rainbow"
        assert instance.effect == "Rainbow"

    def test_supported_effects_property(self, mock_device):
        """Test supported_effects property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        effects = instance.supported_effects

        assert "Off" in effects
        assert "Rainbow" in effects
        assert len(effects) >= 11  # From SUPPORTED_EFFECTS in const.py


class TestBeurerDiagnosticProperties:
    """Tests for diagnostic/debugging properties."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_last_raw_notification_property(self, mock_device):
        """Test last_raw_notification property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.last_raw_notification is None

        instance._last_raw_notification = "DEADBEEF"
        assert instance.last_raw_notification == "DEADBEEF"

    def test_last_unknown_notification_property(self, mock_device):
        """Test last_unknown_notification property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.last_unknown_notification is None

        instance._last_unknown_notification = "CAFEBABE"
        assert instance.last_unknown_notification == "CAFEBABE"

    def test_last_notification_version_property(self, mock_device):
        """Test last_notification_version property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.last_notification_version is None

        instance._last_notification_version = 2
        assert instance.last_notification_version == 2

    def test_heartbeat_count_property(self, mock_device):
        """Test heartbeat_count property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.heartbeat_count == 0

        instance._heartbeat_count = 5
        assert instance.heartbeat_count == 5


class TestBeurerTimerProperties:
    """Tests for timer-related properties."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_timer_active_property(self, mock_device):
        """Test timer_active property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.timer_active is False

        instance._timer_active = True
        assert instance.timer_active is True

    def test_timer_minutes_when_inactive(self, mock_device):
        """Test timer_minutes returns None when timer inactive."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._timer_active = False
        instance._timer_minutes = 30

        assert instance.timer_minutes is None

    def test_timer_minutes_when_active(self, mock_device):
        """Test timer_minutes returns value when timer active."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._timer_active = True
        instance._timer_minutes = 30

        assert instance.timer_minutes == 30


class TestBeurerTherapyProperties:
    """Tests for therapy tracking properties."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_sunrise_simulation_property(self, mock_device):
        """Test sunrise_simulation property creates on first access."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )
        from custom_components.beurer_daylight_lamps.therapy import SunriseSimulation

        instance = BeurerInstance(mock_device)
        assert instance._sunrise_simulation is None

        sim = instance.sunrise_simulation
        assert sim is not None
        assert isinstance(sim, SunriseSimulation)

        # Second access returns same instance
        assert instance.sunrise_simulation is sim

    def test_therapy_tracker_property(self, mock_device):
        """Test therapy_tracker property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )
        from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

        instance = BeurerInstance(mock_device)
        assert isinstance(instance.therapy_tracker, TherapyTracker)

    def test_therapy_today_minutes_property(self, mock_device):
        """Test therapy_today_minutes delegates to tracker."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.therapy_today_minutes == 0.0

    def test_therapy_week_minutes_property(self, mock_device):
        """Test therapy_week_minutes delegates to tracker."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.therapy_week_minutes == 0.0

    def test_therapy_goal_reached_property(self, mock_device):
        """Test therapy_goal_reached delegates to tracker."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.therapy_goal_reached is False

    def test_therapy_goal_progress_pct_property(self, mock_device):
        """Test therapy_goal_progress_pct delegates to tracker."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.therapy_goal_progress_pct == 0

    def test_therapy_daily_goal_property(self, mock_device):
        """Test therapy_daily_goal property."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        assert instance.therapy_daily_goal == 30  # Default

    def test_set_therapy_daily_goal(self, mock_device):
        """Test set_therapy_daily_goal method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        instance.set_therapy_daily_goal(45)
        assert instance.therapy_daily_goal == 45

    def test_set_therapy_daily_goal_clamps_min(self, mock_device):
        """Test set_therapy_daily_goal clamps minimum to 1."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        instance.set_therapy_daily_goal(0)
        assert instance.therapy_daily_goal == 1

    def test_set_therapy_daily_goal_clamps_max(self, mock_device):
        """Test set_therapy_daily_goal clamps maximum to 120."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        instance.set_therapy_daily_goal(200)
        assert instance.therapy_daily_goal == 120


class TestBeurerBleDeviceUpdate:
    """Tests for BLE device update functionality."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_update_ble_device_same_address(self, mock_device):
        """Test update_ble_device updates when address matches."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)

        new_device = MagicMock()
        new_device.address = "AA:BB:CC:DD:EE:FF"
        new_device.name = "TL100-Proxy"

        instance.update_ble_device(new_device)

        assert instance._ble_device is new_device

    def test_update_ble_device_different_address(self, mock_device):
        """Test update_ble_device ignores different address."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        original_device = instance._ble_device

        new_device = MagicMock()
        new_device.address = "11:22:33:44:55:66"
        new_device.name = "Other Device"

        instance.update_ble_device(new_device)

        assert instance._ble_device is original_device

    def test_update_ble_device_none(self, mock_device):
        """Test update_ble_device handles None gracefully."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        original_device = instance._ble_device

        instance.update_ble_device(None)

        assert instance._ble_device is original_device


class TestBeurerDisconnectCallback:
    """Tests for disconnect callback handling."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    def test_on_disconnect_resets_state(self, mock_device):
        """Test _on_disconnect resets connection state."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = True
        instance._light_on = True
        instance._color_on = True
        instance._write_uuid = "write-uuid"
        instance._read_uuid = "read-uuid"

        mock_client = MagicMock()
        instance._on_disconnect(mock_client)

        assert instance._available is False
        assert instance._light_on is False
        assert instance._color_on is False
        assert instance._write_uuid is None
        assert instance._read_uuid is None


class TestBeurerWriteMethod:
    """Tests for the _write method."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_write_no_write_uuid(self, mock_device):
        """Test _write returns False if no write UUID available."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._write_uuid = None

        result = await instance._write(bytearray([0x01, 0x02]))
        assert result is False

    @pytest.mark.asyncio
    async def test_write_success(self, mock_device):
        """Test _write succeeds with valid client and UUID."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance._write(bytearray([0x01, 0x02]))
        assert result is True
        instance._client.write_gatt_char.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_bleak_error(self, mock_device):
        """Test _write handles BleakError gracefully."""
        from bleak.exc import BleakError

        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock(side_effect=BleakError("Test error"))
        instance._client.disconnect = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance._write(bytearray([0x01, 0x02]))
        assert result is False

    @pytest.mark.asyncio
    async def test_write_timeout_error(self, mock_device):
        """Test _write handles TimeoutError gracefully."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock(side_effect=TimeoutError("Timeout"))
        instance._client.disconnect = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance._write(bytearray([0x01, 0x02]))
        assert result is False

    @pytest.mark.asyncio
    async def test_write_os_error(self, mock_device):
        """Test _write handles OSError gracefully."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock(side_effect=OSError("OS Error"))
        instance._client.disconnect = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance._write(bytearray([0x01, 0x02]))
        assert result is False


class TestBeurerSendPacket:
    """Tests for the _send_packet method."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_send_packet_builds_correct_packet(self, mock_device):
        """Test _send_packet builds correct packet structure."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance._send_packet([0x30, 0x01])
        assert result is True

        # Verify packet structure
        call_args = instance._client.write_gatt_char.call_args
        packet = call_args[0][1]

        # Check header
        assert packet[0] == 0xFE
        assert packet[1] == 0xEF
        assert packet[2] == 0x0A
        # Check trailer
        assert packet[-3] == 0x55
        assert packet[-2] == 0x0D
        assert packet[-1] == 0x0A


class TestBeurerCommandMethods:
    """Tests for command methods."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_set_color(self, mock_device):
        """Test set_color method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True  # Already in RGB mode

        await instance.set_color((255, 128, 64))

        assert instance._rgb_color == (255, 128, 64)
        assert instance._mode.value == "rgb"

    @pytest.mark.asyncio
    async def test_set_color_switches_mode(self, mock_device):
        """Test set_color switches to RGB mode if needed."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = False  # Not in RGB mode
        instance._light_on = True

        await instance.set_color((100, 150, 200))

        assert instance._color_on is True
        assert instance._light_on is False
        assert instance._rgb_color == (100, 150, 200)

    @pytest.mark.asyncio
    async def test_set_color_with_brightness(self, mock_device):
        """Test set_color_with_brightness method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True

        await instance.set_color_with_brightness((255, 0, 0), brightness=200)

        assert instance._rgb_color == (255, 0, 0)
        assert instance._color_brightness == 200

    @pytest.mark.asyncio
    async def test_set_color_brightness(self, mock_device):
        """Test set_color_brightness method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True

        await instance.set_color_brightness(180)

        assert instance._color_brightness == 180

    @pytest.mark.asyncio
    async def test_set_color_brightness_none_defaults_to_255(self, mock_device):
        """Test set_color_brightness with None defaults to 255."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True

        await instance.set_color_brightness(None)

        assert instance._color_brightness == 255

    @pytest.mark.asyncio
    async def test_set_color_with_brightness_clears_effect(self, mock_device):
        """Test set_color_with_brightness clears running effect."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True
        instance._effect = "Rainbow"  # Active effect

        await instance.set_color_with_brightness((0, 255, 0))

        assert instance._effect == "Off"


class TestBeurerWhiteModeCommands:
    """Tests for white mode commands."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_set_white(self, mock_device):
        """Test set_white method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._light_on = True

        await instance.set_white(200)

        assert instance._brightness == 200

    @pytest.mark.asyncio
    async def test_set_white_switches_mode(self, mock_device):
        """Test set_white switches to white mode if needed."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._light_on = False
        instance._color_on = True

        await instance.set_white(150)

        assert instance._light_on is True
        assert instance._color_on is False
        assert instance._brightness == 150

    @pytest.mark.asyncio
    async def test_set_white_none_defaults_to_255(self, mock_device):
        """Test set_white with None defaults to 255."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._light_on = True

        await instance.set_white(None)

        assert instance._brightness == 255


class TestBeurerTurnOnOff:
    """Tests for turn_on and turn_off methods."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_device):
        """Test turn_off method."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._light_on = True

        await instance.turn_off()

        assert instance._light_on is False
        assert instance._color_on is False

    @pytest.mark.asyncio
    async def test_turn_on_white_mode(self, mock_device):
        """Test turn_on in white mode."""
        from homeassistant.components.light import ColorMode

        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._mode = ColorMode.WHITE

        await instance.turn_on()

        assert instance._light_on is True
        assert instance._color_on is False

    @pytest.mark.asyncio
    async def test_turn_on_rgb_mode(self, mock_device):
        """Test turn_on in RGB mode."""
        from homeassistant.components.light import ColorMode

        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._mode = ColorMode.RGB

        await instance.turn_on()

        assert instance._color_on is True
        assert instance._light_on is False


class TestBeurerTimerMethod:
    """Tests for timer method."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_set_timer_valid(self, mock_device):
        """Test set_timer with valid minutes."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance.set_timer(30)

        assert result is True
        instance._client.write_gatt_char.assert_called()

    @pytest.mark.asyncio
    async def test_set_timer_invalid_low(self, mock_device):
        """Test set_timer rejects values below 1."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance.set_timer(0)

        assert result is False

    @pytest.mark.asyncio
    async def test_set_timer_invalid_high(self, mock_device):
        """Test set_timer rejects values above 120."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance.set_timer(121)

        assert result is False

    @pytest.mark.asyncio
    async def test_set_timer_boundary_min(self, mock_device):
        """Test set_timer at minimum boundary (1)."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance.set_timer(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_timer_boundary_max(self, mock_device):
        """Test set_timer at maximum boundary (120)."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        result = await instance.set_timer(120)

        assert result is True


class TestBeurerEffectMethod:
    """Tests for set_effect method."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_set_effect_rainbow(self, mock_device):
        """Test set_effect with Rainbow."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True

        await instance.set_effect("Rainbow")

        assert instance._effect == "Rainbow"

    @pytest.mark.asyncio
    async def test_set_effect_switches_to_rgb_mode(self, mock_device):
        """Test set_effect switches to RGB mode if needed."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = False
        instance._light_on = True

        await instance.set_effect("Summer")

        assert instance._color_on is True
        assert instance._effect == "Summer"

    @pytest.mark.asyncio
    async def test_set_effect_off(self, mock_device):
        """Test set_effect Off."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True
        instance._effect = "Rainbow"

        await instance.set_effect("Off")

        assert instance._effect == "Off"


class TestBeurerSendPacketIntegration:
    """Integration tests for _send_packet with command methods."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_set_effect_none_defaults_to_off(self, mock_device):
        """Test set_effect with None defaults to Off."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = True

        await instance.set_effect(None)

        assert instance._effect == "Off"


class TestNotificationEdgeCases:
    """Edge case tests for notification parsing."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_heartbeat_notification(self, mock_device):
        """Test short payload (heartbeat/ACK) updates last_seen."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._available = False
        initial_heartbeat = instance._heartbeat_count
        char = MagicMock()

        # Short payload (payload_len < 0x08) - heartbeat packet
        data = bytearray([0x00] * 11)
        data[6] = 0x04  # payload_len = 0x04 (heartbeat)

        await instance._handle_notification(char, data)

        assert instance._heartbeat_count == initial_heartbeat + 1
        assert instance._available is True  # Should become available

    @pytest.mark.asyncio
    async def test_shutdown_notification(self, mock_device):
        """Test version 0 (shutdown) triggers disconnect."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.disconnect = AsyncMock()
        char = MagicMock()

        # Shutdown notification: version=0
        data = bytearray([0x00] * 11)
        data[6] = 0x08  # payload_len = 0x08 (status packet)
        data[8] = 0  # version = shutdown

        await instance._handle_notification(char, data)

        # Disconnect should be triggered (async)

    @pytest.mark.asyncio
    async def test_unknown_version_notification(self, mock_device):
        """Test unknown version stores for reverse engineering."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # Unknown version notification: version=99
        data = bytearray([0x00] * 11)
        data[6] = 0x08  # payload_len = 0x08 (status packet)
        data[8] = 99  # unknown version

        await instance._handle_notification(char, data)

        assert instance._last_unknown_notification is not None

    @pytest.mark.asyncio
    async def test_rgb_therapy_tracking_white_ish(self, mock_device):
        """Test therapy tracking detects white-ish light."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # RGB notification with white-ish color at high brightness
        # version=2, on=1, brightness=100%, RGB=(255,255,255), effect=0
        data = bytearray([0x00] * 17)
        data[6] = 0x0C  # payload_len = 0x0C (RGB status)
        data[8] = 2  # version = RGB mode
        data[9] = 1  # on
        data[10] = 100  # brightness 100%
        data[13] = 255  # R
        data[14] = 255  # G
        data[15] = 255  # B
        data[16] = 0    # effect = Off

        await instance._handle_notification(char, data)

        assert instance._color_on is True
        assert instance._rgb_color == (255, 255, 255)
        # Therapy tracker should have started

    @pytest.mark.asyncio
    async def test_rgb_therapy_tracking_non_white(self, mock_device):
        """Test therapy tracking with non-white color."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # RGB notification with red color
        data = bytearray([0x00] * 17)
        data[6] = 0x0C  # payload_len = 0x0C (RGB status)
        data[8] = 2  # version = RGB mode
        data[9] = 1  # on
        data[10] = 100  # brightness 100%
        data[13] = 255  # R
        data[14] = 0    # G
        data[15] = 0    # B
        data[16] = 0    # effect = Off

        await instance._handle_notification(char, data)

        assert instance._rgb_color == (255, 0, 0)
        # Non-white color should not start therapy session

    @pytest.mark.asyncio
    async def test_rgb_off_ends_therapy_session(self, mock_device):
        """Test RGB turning off ends therapy session."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._color_on = True
        char = MagicMock()

        # RGB notification with off state
        data = bytearray([0x00] * 17)
        data[6] = 0x0C  # payload_len = 0x0C (RGB status)
        data[8] = 2  # version = RGB mode
        data[9] = 0  # OFF

        await instance._handle_notification(char, data)

        assert instance._color_on is False

    @pytest.mark.asyncio
    async def test_device_off_ends_therapy_session(self, mock_device):
        """Test device off (version 255) ends therapy session."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._light_on = True
        instance._color_on = True
        char = MagicMock()

        # Device off notification
        data = bytearray([0x00] * 11)
        data[6] = 0x08  # payload_len
        data[8] = 255  # version = device off

        await instance._handle_notification(char, data)

        assert instance._light_on is False
        assert instance._color_on is False

    @pytest.mark.asyncio
    async def test_white_mode_brightness_calculation(self, mock_device):
        """Test white mode brightness is correctly scaled."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # White mode at 50% brightness
        data = bytearray([0x00] * 11)
        data[6] = 0x08  # payload_len
        data[8] = 1  # version = white mode
        data[9] = 1  # on
        data[10] = 50  # 50% brightness

        await instance._handle_notification(char, data)

        # 50% of 255 = 127.5 -> 127
        assert instance._brightness == 127

    @pytest.mark.asyncio
    async def test_rgb_effect_index_bounds(self, mock_device):
        """Test RGB effect index is bounded by supported effects."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        char = MagicMock()

        # RGB mode with valid effect index
        data = bytearray([0x00] * 17)
        data[6] = 0x0C
        data[8] = 2  # version = RGB mode
        data[9] = 1  # on
        data[10] = 100
        data[13] = 255
        data[14] = 0
        data[15] = 0
        data[16] = 2  # effect index = Rainbow (index 2)

        await instance._handle_notification(char, data)

        assert instance._effect == "Rainbow"

    @pytest.mark.asyncio
    async def test_notification_triggers_update_callback(self, mock_device):
        """Test notification triggers registered callbacks."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        callback = MagicMock()
        instance.set_update_callback(callback)
        instance._available = False
        char = MagicMock()

        # White mode notification (triggers update when available changes)
        data = bytearray([0x00] * 11)
        data[6] = 0x08
        data[8] = 1  # white mode
        data[9] = 1  # on
        data[10] = 100

        await instance._handle_notification(char, data)

        callback.assert_called()


class TestRequestStatusMethod:
    """Tests for _request_status method."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_request_status_sends_both_modes(self, mock_device):
        """Test _request_status requests both white and RGB status."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"

        await instance._request_status()

        # Should have sent 2 packets (white and RGB status)
        assert instance._client.write_gatt_char.call_count == 2


class TestTriggerUpdateMethod:
    """Tests for _trigger_update method."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_trigger_update_calls_all_callbacks(self, mock_device):
        """Test _trigger_update calls all registered callbacks."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        callback1 = MagicMock()
        callback2 = MagicMock()
        instance.set_update_callback(callback1)
        instance.set_update_callback(callback2)

        await instance._trigger_update()

        callback1.assert_called_once()
        callback2.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_update_no_callbacks(self, mock_device):
        """Test _trigger_update with no callbacks does nothing."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        # No callbacks registered

        # Should not raise
        await instance._trigger_update()


class TestColorModeModeSwitching:
    """Tests for mode switching edge cases."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock BLE device."""
        device = MagicMock()
        device.address = "AA:BB:CC:DD:EE:FF"
        device.name = "TL100"
        return device

    @pytest.mark.asyncio
    async def test_set_color_clears_effect_when_active(self, mock_device):
        """Test set_color clears effect when an effect is active."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = False
        instance._effect = "Rainbow"

        await instance.set_color((100, 100, 100))

        # Effect should be cleared when setting a new color
        assert instance._effect == "Off"

    @pytest.mark.asyncio
    async def test_set_color_brightness_switches_mode(self, mock_device):
        """Test set_color_brightness switches to RGB mode if not active."""
        from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
            BeurerInstance,
        )

        instance = BeurerInstance(mock_device)
        instance._client = MagicMock()
        instance._client.is_connected = True
        instance._client.write_gatt_char = AsyncMock()
        instance._write_uuid = "test-uuid"
        instance._color_on = False
        instance._light_on = True

        await instance.set_color_brightness(200)

        assert instance._color_on is True
        assert instance._light_on is False
