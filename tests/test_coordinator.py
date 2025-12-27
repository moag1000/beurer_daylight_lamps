"""Test Beurer Daylight Lamps coordinator."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.coordinator import (
    UPDATE_INTERVAL,
    BeurerDataUpdateCoordinator,
)


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_update_interval(self) -> None:
        """Test update interval is 5 minutes."""
        assert UPDATE_INTERVAL == timedelta(minutes=5)


# =============================================================================
# Test BeurerDataUpdateCoordinator Initialization
# =============================================================================


class TestCoordinatorInitialization:
    """Tests for coordinator initialization."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_on = True
        instance.available = True
        instance.ble_available = True
        instance.is_connected = True
        instance.color_mode = ColorMode.WHITE
        instance.color_on = False
        instance.white_on = True
        instance.white_brightness = 255
        instance.color_brightness = 128
        instance.rgb_color = (255, 128, 64)
        instance.effect = "Off"
        instance.rssi = -60
        instance.last_seen = None
        instance.last_raw_notification = None
        instance.timer_active = False
        instance.timer_minutes = 0
        instance.therapy_today_minutes = 30
        instance.therapy_week_minutes = 120
        instance.therapy_goal_reached = False
        instance.therapy_goal_progress_pct = 50.0
        instance.therapy_daily_goal = 60
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        instance.update = AsyncMock()
        return instance

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        return hass

    def test_initialization(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test coordinator initialization."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        assert coordinator.instance == mock_instance
        assert coordinator.device_name == "Test Lamp"
        assert coordinator.name == "Beurer Test Lamp"
        assert coordinator.update_interval == UPDATE_INTERVAL

    def test_registers_update_callback(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test that coordinator registers for push updates."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        mock_instance.set_update_callback.assert_called_once_with(
            coordinator._handle_push_update
        )


# =============================================================================
# Test Data Retrieval
# =============================================================================


class TestGetCurrentData:
    """Tests for _get_current_data method."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance with complete data."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_on = True
        instance.available = True
        instance.ble_available = True
        instance.is_connected = True
        instance.color_mode = ColorMode.RGB
        instance.color_on = True
        instance.white_on = False
        instance.white_brightness = 200
        instance.color_brightness = 150
        instance.rgb_color = (100, 150, 200)
        instance.effect = "Rainbow"
        instance.rssi = -55
        instance.last_seen = "2024-01-01T12:00:00"
        instance.last_raw_notification = "0x123456"
        instance.timer_active = True
        instance.timer_minutes = 30
        instance.therapy_today_minutes = 45
        instance.therapy_week_minutes = 180
        instance.therapy_goal_reached = True
        instance.therapy_goal_progress_pct = 100.0
        instance.therapy_daily_goal = 45
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        return hass

    def test_get_current_data_all_fields(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test that _get_current_data returns all expected fields."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        data = coordinator._get_current_data()

        # Power state
        assert data["is_on"] is True
        assert data["available"] is True
        assert data["ble_available"] is True
        assert data["connected"] is True

        # Light state
        assert data["color_mode"] == ColorMode.RGB
        assert data["color_on"] is True
        assert data["white_on"] is False
        assert data["white_brightness"] == 200
        assert data["color_brightness"] == 150
        assert data["rgb_color"] == (100, 150, 200)
        assert data["effect"] == "Rainbow"

        # Diagnostics
        assert data["rssi"] == -55
        assert data["last_seen"] == "2024-01-01T12:00:00"
        assert data["last_raw_notification"] == "0x123456"

        # Timer
        assert data["timer_active"] is True
        assert data["timer_minutes"] == 30

        # Therapy
        assert data["therapy_today_minutes"] == 45
        assert data["therapy_week_minutes"] == 180
        assert data["therapy_goal_reached"] is True
        assert data["therapy_goal_progress_pct"] == 100.0
        assert data["therapy_daily_goal"] == 45


# =============================================================================
# Test Push Updates
# =============================================================================


class TestPushUpdates:
    """Tests for push update handling."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_on = True
        instance.available = True
        instance.ble_available = True
        instance.is_connected = True
        instance.color_mode = ColorMode.WHITE
        instance.color_on = False
        instance.white_on = True
        instance.white_brightness = 255
        instance.color_brightness = 128
        instance.rgb_color = (255, 255, 255)
        instance.effect = "Off"
        instance.rssi = -60
        instance.last_seen = None
        instance.last_raw_notification = None
        instance.timer_active = False
        instance.timer_minutes = 0
        instance.therapy_today_minutes = 0
        instance.therapy_week_minutes = 0
        instance.therapy_goal_reached = False
        instance.therapy_goal_progress_pct = 0.0
        instance.therapy_daily_goal = 30
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        return hass

    def test_handle_push_update_sets_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test that push update sets coordinator data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        with patch.object(coordinator, "async_set_updated_data") as mock_set:
            coordinator._handle_push_update()

            mock_set.assert_called_once()
            # Verify the data passed matches current state
            call_args = mock_set.call_args[0][0]
            assert call_args["is_on"] is True
            assert call_args["available"] is True


# =============================================================================
# Test Periodic Updates
# =============================================================================


class TestPeriodicUpdates:
    """Tests for periodic update handling."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_on = False
        instance.available = True
        instance.ble_available = True
        instance.is_connected = False
        instance.color_mode = ColorMode.WHITE
        instance.color_on = False
        instance.white_on = True
        instance.white_brightness = 128
        instance.color_brightness = 64
        instance.rgb_color = None
        instance.effect = "Off"
        instance.rssi = -70
        instance.last_seen = None
        instance.last_raw_notification = None
        instance.timer_active = False
        instance.timer_minutes = 0
        instance.therapy_today_minutes = 15
        instance.therapy_week_minutes = 60
        instance.therapy_goal_reached = False
        instance.therapy_goal_progress_pct = 25.0
        instance.therapy_daily_goal = 60
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        instance.update = AsyncMock()
        return instance

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        return hass

    @pytest.mark.asyncio
    async def test_async_update_data_when_available(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test periodic update calls instance.update when BLE available."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        data = await coordinator._async_update_data()

        mock_instance.update.assert_called_once()
        assert data["is_on"] is False
        assert data["therapy_today_minutes"] == 15

    @pytest.mark.asyncio
    async def test_async_update_data_skips_when_unavailable(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test periodic update skips when BLE not available."""
        mock_instance.ble_available = False
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        data = await coordinator._async_update_data()

        mock_instance.update.assert_not_called()
        # Still returns current data
        assert data["ble_available"] is False

    @pytest.mark.asyncio
    async def test_async_update_data_handles_exception(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test periodic update handles exceptions gracefully."""
        mock_instance.update = AsyncMock(side_effect=Exception("BLE error"))
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        # Should not raise, returns current data instead
        data = await coordinator._async_update_data()

        assert data is not None
        assert data["available"] is True


# =============================================================================
# Test Shutdown
# =============================================================================


class TestShutdown:
    """Tests for coordinator shutdown."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.is_on = True
        instance.available = True
        instance.ble_available = True
        instance.is_connected = True
        instance.color_mode = ColorMode.WHITE
        instance.color_on = False
        instance.white_on = True
        instance.white_brightness = 255
        instance.color_brightness = 128
        instance.rgb_color = None
        instance.effect = "Off"
        instance.rssi = -60
        instance.last_seen = None
        instance.last_raw_notification = None
        instance.timer_active = False
        instance.timer_minutes = 0
        instance.therapy_today_minutes = 0
        instance.therapy_week_minutes = 0
        instance.therapy_goal_reached = False
        instance.therapy_goal_progress_pct = 0.0
        instance.therapy_daily_goal = 30
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        return hass

    @pytest.mark.asyncio
    async def test_async_shutdown_removes_callback(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test shutdown removes update callback."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )

        with patch.object(
            coordinator.__class__.__bases__[0], "async_shutdown", new_callable=AsyncMock
        ):
            await coordinator.async_shutdown()

        mock_instance.remove_update_callback.assert_called_once_with(
            coordinator._handle_push_update
        )


# =============================================================================
# Test Convenience Properties
# =============================================================================


class TestConvenienceProperties:
    """Tests for convenience properties."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        instance.set_update_callback = MagicMock()
        instance.remove_update_callback = MagicMock()
        return instance

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        return hass

    def test_is_on_with_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test is_on property with data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {"is_on": True}

        assert coordinator.is_on is True

    def test_is_on_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test is_on property without data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.is_on is None

    def test_available_with_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test available property with data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {"available": True}

        assert coordinator.available is True

    def test_available_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test available property without data returns False."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.available is False

    def test_available_missing_key(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test available property with missing key returns False."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {}

        assert coordinator.available is False

    def test_color_mode_with_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test color_mode property with data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {"color_mode": ColorMode.RGB}

        assert coordinator.color_mode == ColorMode.RGB

    def test_color_mode_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test color_mode property without data returns WHITE."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.color_mode == ColorMode.WHITE

    def test_color_mode_missing_key(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test color_mode property with missing key returns WHITE."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {}

        assert coordinator.color_mode == ColorMode.WHITE

    def test_brightness_white_mode(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test brightness property in white mode."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {
            "color_mode": ColorMode.WHITE,
            "white_brightness": 200,
            "color_brightness": 100,
        }

        assert coordinator.brightness == 200

    def test_brightness_rgb_mode(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test brightness property in RGB mode."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {
            "color_mode": ColorMode.RGB,
            "white_brightness": 200,
            "color_brightness": 100,
        }

        assert coordinator.brightness == 100

    def test_brightness_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test brightness property without data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.brightness is None

    def test_rgb_color_with_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test rgb_color property with data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {"rgb_color": (255, 128, 64)}

        assert coordinator.rgb_color == (255, 128, 64)

    def test_rgb_color_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test rgb_color property without data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.rgb_color is None

    def test_effect_with_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test effect property with data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {"effect": "Rainbow"}

        assert coordinator.effect == "Rainbow"

    def test_effect_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test effect property without data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.effect is None

    def test_rssi_with_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test rssi property with data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = {"rssi": -55}

        assert coordinator.rssi == -55

    def test_rssi_without_data(
        self, mock_hass: MagicMock, mock_instance: MagicMock
    ) -> None:
        """Test rssi property without data."""
        coordinator = BeurerDataUpdateCoordinator(
            mock_hass, mock_instance, "Test Lamp"
        )
        coordinator.data = None

        assert coordinator.rssi is None
