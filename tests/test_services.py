"""Tests for Beurer Daylight Lamps services."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant

# Import service constants and schemas from __init__.py
from custom_components.beurer_daylight_lamps import (
    ATTR_COMMAND,
    ATTR_DEVICE_ID,
    ATTR_DURATION,
    ATTR_END_BRIGHTNESS,
    ATTR_MINUTES,
    ATTR_PRESET,
    ATTR_PROFILE,
    PRESETS,
    SERVICE_APPLY_PRESET,
    SERVICE_RAW_SCHEMA,
    SERVICE_SCHEMA,
    SERVICE_SEND_RAW,
    SERVICE_SET_TIMER,
    SERVICE_START_SUNRISE,
    SERVICE_START_SUNSET,
    SERVICE_STOP_SIMULATION,
    SERVICE_SUNRISE_SCHEMA,
    SERVICE_SUNSET_SCHEMA,
    SERVICE_TIMER_SCHEMA,
    SUNRISE_PROFILES,
    _get_instance_for_device,
)
from custom_components.beurer_daylight_lamps.const import DOMAIN
from custom_components.beurer_daylight_lamps.therapy import SunriseProfile


# =============================================================================
# SCHEMA VALIDATION TESTS (Pure unit tests - no Home Assistant required)
# =============================================================================


class TestServiceSchemas:
    """Test service schema validation (no HA dependencies)."""

    # -------------------------------------------------------------------------
    # PRESET SCHEMA TESTS
    # -------------------------------------------------------------------------

    def test_preset_schema_valid(self) -> None:
        """Test preset schema with valid data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_PRESET: "daylight_therapy",
        }
        result = SERVICE_SCHEMA(data)
        assert result[ATTR_DEVICE_ID] == "abc123"
        assert result[ATTR_PRESET] == "daylight_therapy"

    def test_preset_schema_all_presets(self) -> None:
        """Test all preset names are valid in schema."""
        for preset_name in PRESETS:
            data = {
                ATTR_DEVICE_ID: "abc123",
                ATTR_PRESET: preset_name,
            }
            result = SERVICE_SCHEMA(data)
            assert result[ATTR_PRESET] == preset_name

    def test_preset_schema_invalid_preset(self) -> None:
        """Test preset schema rejects invalid preset name."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_PRESET: "invalid_preset_name",
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SCHEMA(data)

    def test_preset_schema_missing_device_id(self) -> None:
        """Test preset schema requires device_id."""
        data = {
            ATTR_PRESET: "daylight_therapy",
        }
        with pytest.raises(vol.MultipleInvalid):
            SERVICE_SCHEMA(data)

    def test_preset_schema_missing_preset(self) -> None:
        """Test preset schema requires preset."""
        data = {
            ATTR_DEVICE_ID: "abc123",
        }
        with pytest.raises(vol.MultipleInvalid):
            SERVICE_SCHEMA(data)

    # -------------------------------------------------------------------------
    # RAW COMMAND SCHEMA TESTS
    # -------------------------------------------------------------------------

    def test_raw_schema_valid(self) -> None:
        """Test raw command schema with valid data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_COMMAND: "3E 1E",
        }
        result = SERVICE_RAW_SCHEMA(data)
        assert result[ATTR_DEVICE_ID] == "abc123"
        assert result[ATTR_COMMAND] == "3E 1E"

    def test_raw_schema_hex_no_spaces(self) -> None:
        """Test raw command accepts hex without spaces."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_COMMAND: "3E1E",
        }
        result = SERVICE_RAW_SCHEMA(data)
        assert result[ATTR_COMMAND] == "3E1E"

    def test_raw_schema_missing_command(self) -> None:
        """Test raw command schema requires command."""
        data = {
            ATTR_DEVICE_ID: "abc123",
        }
        with pytest.raises(vol.MultipleInvalid):
            SERVICE_RAW_SCHEMA(data)

    # -------------------------------------------------------------------------
    # TIMER SCHEMA TESTS
    # -------------------------------------------------------------------------

    def test_timer_schema_valid(self) -> None:
        """Test timer schema with valid data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_MINUTES: 30,
        }
        result = SERVICE_TIMER_SCHEMA(data)
        assert result[ATTR_DEVICE_ID] == "abc123"
        assert result[ATTR_MINUTES] == 30

    def test_timer_schema_string_minutes(self) -> None:
        """Test timer schema coerces string to int."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_MINUTES: "30",
        }
        result = SERVICE_TIMER_SCHEMA(data)
        assert result[ATTR_MINUTES] == 30

    def test_timer_schema_min_value(self) -> None:
        """Test timer schema accepts minimum value (1)."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_MINUTES: 1,
        }
        result = SERVICE_TIMER_SCHEMA(data)
        assert result[ATTR_MINUTES] == 1

    def test_timer_schema_max_value(self) -> None:
        """Test timer schema accepts maximum value (240)."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_MINUTES: 240,
        }
        result = SERVICE_TIMER_SCHEMA(data)
        assert result[ATTR_MINUTES] == 240

    def test_timer_schema_below_min(self) -> None:
        """Test timer schema rejects value below minimum."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_MINUTES: 0,
        }
        with pytest.raises(vol.Invalid):
            SERVICE_TIMER_SCHEMA(data)

    def test_timer_schema_above_max(self) -> None:
        """Test timer schema rejects value above maximum."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_MINUTES: 241,
        }
        with pytest.raises(vol.Invalid):
            SERVICE_TIMER_SCHEMA(data)

    # -------------------------------------------------------------------------
    # SUNRISE SCHEMA TESTS
    # -------------------------------------------------------------------------

    def test_sunrise_schema_valid_minimal(self) -> None:
        """Test sunrise schema with minimal required data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
        }
        result = SERVICE_SUNRISE_SCHEMA(data)
        assert result[ATTR_DEVICE_ID] == "abc123"
        assert result[ATTR_DURATION] == 15  # default
        assert result[ATTR_PROFILE] == "natural"  # default

    def test_sunrise_schema_valid_full(self) -> None:
        """Test sunrise schema with all optional data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_DURATION: 30,
            ATTR_PROFILE: "gentle",
        }
        result = SERVICE_SUNRISE_SCHEMA(data)
        assert result[ATTR_DURATION] == 30
        assert result[ATTR_PROFILE] == "gentle"

    def test_sunrise_schema_all_profiles(self) -> None:
        """Test all sunrise profiles are valid."""
        for profile in SUNRISE_PROFILES:
            data = {
                ATTR_DEVICE_ID: "abc123",
                ATTR_PROFILE: profile,
            }
            result = SERVICE_SUNRISE_SCHEMA(data)
            assert result[ATTR_PROFILE] == profile

    def test_sunrise_schema_invalid_profile(self) -> None:
        """Test sunrise schema rejects invalid profile."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_PROFILE: "invalid_profile",
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SUNRISE_SCHEMA(data)

    def test_sunrise_schema_duration_min(self) -> None:
        """Test sunrise schema accepts minimum duration (1)."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_DURATION: 1,
        }
        result = SERVICE_SUNRISE_SCHEMA(data)
        assert result[ATTR_DURATION] == 1

    def test_sunrise_schema_duration_max(self) -> None:
        """Test sunrise schema accepts maximum duration (60)."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_DURATION: 60,
        }
        result = SERVICE_SUNRISE_SCHEMA(data)
        assert result[ATTR_DURATION] == 60

    def test_sunrise_schema_duration_below_min(self) -> None:
        """Test sunrise schema rejects duration below minimum."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_DURATION: 0,
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SUNRISE_SCHEMA(data)

    def test_sunrise_schema_duration_above_max(self) -> None:
        """Test sunrise schema rejects duration above maximum."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_DURATION: 61,
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SUNRISE_SCHEMA(data)

    # -------------------------------------------------------------------------
    # SUNSET SCHEMA TESTS
    # -------------------------------------------------------------------------

    def test_sunset_schema_valid_minimal(self) -> None:
        """Test sunset schema with minimal required data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
        }
        result = SERVICE_SUNSET_SCHEMA(data)
        assert result[ATTR_DEVICE_ID] == "abc123"
        assert result[ATTR_DURATION] == 30  # default
        assert result[ATTR_END_BRIGHTNESS] == 0  # default

    def test_sunset_schema_valid_full(self) -> None:
        """Test sunset schema with all optional data."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_DURATION: 45,
            ATTR_END_BRIGHTNESS: 20,
        }
        result = SERVICE_SUNSET_SCHEMA(data)
        assert result[ATTR_DURATION] == 45
        assert result[ATTR_END_BRIGHTNESS] == 20

    def test_sunset_schema_end_brightness_zero(self) -> None:
        """Test sunset schema accepts 0% brightness (turn off)."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_END_BRIGHTNESS: 0,
        }
        result = SERVICE_SUNSET_SCHEMA(data)
        assert result[ATTR_END_BRIGHTNESS] == 0

    def test_sunset_schema_end_brightness_max(self) -> None:
        """Test sunset schema accepts 100% brightness."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_END_BRIGHTNESS: 100,
        }
        result = SERVICE_SUNSET_SCHEMA(data)
        assert result[ATTR_END_BRIGHTNESS] == 100

    def test_sunset_schema_end_brightness_above_max(self) -> None:
        """Test sunset schema rejects brightness above maximum."""
        data = {
            ATTR_DEVICE_ID: "abc123",
            ATTR_END_BRIGHTNESS: 101,
        }
        with pytest.raises(vol.Invalid):
            SERVICE_SUNSET_SCHEMA(data)


# =============================================================================
# PRESET DEFINITIONS TESTS
# =============================================================================


class TestPresetDefinitions:
    """Test preset configuration definitions."""

    def test_all_presets_have_brightness(self) -> None:
        """Test all presets define brightness."""
        for name, preset in PRESETS.items():
            assert "brightness" in preset, f"Preset '{name}' missing brightness"
            assert 0 <= preset["brightness"] <= 255, f"Preset '{name}' has invalid brightness"

    def test_all_presets_have_color(self) -> None:
        """Test all presets define either rgb or color_temp_kelvin."""
        for name, preset in PRESETS.items():
            has_rgb = "rgb" in preset
            has_kelvin = "color_temp_kelvin" in preset
            assert has_rgb or has_kelvin, f"Preset '{name}' missing color definition"

    def test_preset_rgb_values_valid(self) -> None:
        """Test RGB presets have valid RGB tuples."""
        for name, preset in PRESETS.items():
            if "rgb" in preset:
                rgb = preset["rgb"]
                assert isinstance(rgb, tuple), f"Preset '{name}' rgb is not tuple"
                assert len(rgb) == 3, f"Preset '{name}' rgb has {len(rgb)} values"
                for val in rgb:
                    assert 0 <= val <= 255, f"Preset '{name}' has invalid RGB value"

    def test_preset_kelvin_values_valid(self) -> None:
        """Test color temp presets have valid Kelvin values."""
        for name, preset in PRESETS.items():
            if "color_temp_kelvin" in preset:
                kelvin = preset["color_temp_kelvin"]
                # Typical range for color temperature
                assert 2000 <= kelvin <= 7000, f"Preset '{name}' has unusual Kelvin value {kelvin}"

    def test_expected_presets_exist(self) -> None:
        """Test expected preset names exist."""
        expected = [
            "daylight_therapy",
            "relax",
            "focus",
            "reading",
            "warm_cozy",
            "cool_bright",
            "sunset",
            "night_light",
            "energize",
        ]
        for preset in expected:
            assert preset in PRESETS, f"Expected preset '{preset}' not found"


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGetInstanceForDevice:
    """Test _get_instance_for_device helper function."""

    @pytest.mark.asyncio
    async def test_device_not_found(self, hass: HomeAssistant) -> None:
        """Test returns None when device not found."""
        with patch(
            "custom_components.beurer_daylight_lamps.dr.async_get"
        ) as mock_dr:
            mock_registry = MagicMock()
            mock_registry.async_get.return_value = None
            mock_dr.return_value = mock_registry

            result = _get_instance_for_device(hass, "nonexistent_device", "TEST")
            assert result is None

    @pytest.mark.asyncio
    async def test_no_beurer_config_entry(self, hass: HomeAssistant) -> None:
        """Test returns None when no Beurer config entry found."""
        with patch(
            "custom_components.beurer_daylight_lamps.dr.async_get"
        ) as mock_dr:
            mock_registry = MagicMock()
            mock_device = MagicMock()
            mock_device.config_entries = {"other_entry_id"}
            mock_registry.async_get.return_value = mock_device
            mock_dr.return_value = mock_registry

            # Mock config entries
            mock_entry = MagicMock()
            mock_entry.domain = "other_integration"
            hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)

            result = _get_instance_for_device(hass, "device_id", "TEST")
            assert result is None

    @pytest.mark.asyncio
    async def test_config_entry_not_ready(self, hass: HomeAssistant) -> None:
        """Test returns None when config entry has no runtime_data."""
        with patch(
            "custom_components.beurer_daylight_lamps.dr.async_get"
        ) as mock_dr:
            mock_registry = MagicMock()
            mock_device = MagicMock()
            mock_device.config_entries = {"beurer_entry_id"}
            mock_registry.async_get.return_value = mock_device
            mock_dr.return_value = mock_registry

            # Mock config entry without runtime_data
            mock_entry = MagicMock()
            mock_entry.domain = DOMAIN
            del mock_entry.runtime_data  # Remove attribute
            hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)

            result = _get_instance_for_device(hass, "device_id", "TEST")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_instance_when_found(self, hass: HomeAssistant) -> None:
        """Test returns BeurerInstance when properly configured."""
        with patch(
            "custom_components.beurer_daylight_lamps.dr.async_get"
        ) as mock_dr:
            mock_registry = MagicMock()
            mock_device = MagicMock()
            mock_device.config_entries = {"beurer_entry_id"}
            mock_registry.async_get.return_value = mock_device
            mock_dr.return_value = mock_registry

            # Mock config entry with runtime_data
            mock_instance = MagicMock()
            mock_entry = MagicMock()
            mock_entry.domain = DOMAIN
            mock_entry.runtime_data = mock_instance
            hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)

            result = _get_instance_for_device(hass, "device_id", "TEST")
            assert result is mock_instance


# =============================================================================
# SERVICE HANDLER TESTS (Async tests with mocked HomeAssistant)
# =============================================================================


class TestApplyPresetService:
    """Test apply_preset service handler."""

    @pytest.mark.asyncio
    async def test_apply_preset_with_color_temp(self, hass: HomeAssistant) -> None:
        """Test apply preset with color temperature."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.set_color = AsyncMock()
        mock_instance.set_color_brightness = AsyncMock()

        # Import handler locally to get fresh import
        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            # Setup services
            await _async_setup_services(hass)

            # Call service using hass.services.async_call
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPLY_PRESET,
                {ATTR_DEVICE_ID: "device123", ATTR_PRESET: "daylight_therapy"},
                blocking=True,
            )

            # Verify color was set (daylight_therapy has color_temp_kelvin)
            mock_instance.set_color.assert_called_once()
            mock_instance.set_color_brightness.assert_called_once_with(255)

    @pytest.mark.asyncio
    async def test_apply_preset_with_rgb(self, hass: HomeAssistant) -> None:
        """Test apply preset with RGB color."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.set_color = AsyncMock()
        mock_instance.set_color_brightness = AsyncMock()

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPLY_PRESET,
                {ATTR_DEVICE_ID: "device123", ATTR_PRESET: "sunset"},
                blocking=True,
            )

            # sunset preset has RGB (255, 120, 50)
            mock_instance.set_color.assert_called_once_with((255, 120, 50))
            mock_instance.set_color_brightness.assert_called_once_with(180)

    @pytest.mark.asyncio
    async def test_apply_preset_device_not_found(self, hass: HomeAssistant) -> None:
        """Test apply preset when device not found."""
        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=None,
        ):
            await _async_setup_services(hass)

            # Should not raise, just return early
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPLY_PRESET,
                {ATTR_DEVICE_ID: "device123", ATTR_PRESET: "daylight_therapy"},
                blocking=True,
            )


class TestSendRawCommandService:
    """Test send_raw_command service handler."""

    @pytest.mark.asyncio
    async def test_send_raw_command_with_spaces(self, hass: HomeAssistant) -> None:
        """Test send raw command with space-separated hex."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance._send_packet = AsyncMock(return_value=True)

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_RAW,
                {ATTR_DEVICE_ID: "device123", ATTR_COMMAND: "3E 1E"},
                blocking=True,
            )

            # 3E = 62, 1E = 30 (30 minute timer)
            mock_instance._send_packet.assert_called_once_with([0x3E, 0x1E])

    @pytest.mark.asyncio
    async def test_send_raw_command_without_spaces(self, hass: HomeAssistant) -> None:
        """Test send raw command without spaces."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance._send_packet = AsyncMock(return_value=True)

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_RAW,
                {ATTR_DEVICE_ID: "device123", ATTR_COMMAND: "3E1E"},
                blocking=True,
            )

            mock_instance._send_packet.assert_called_once_with([0x3E, 0x1E])

    @pytest.mark.asyncio
    async def test_send_raw_command_with_0x_prefix(self, hass: HomeAssistant) -> None:
        """Test send raw command with 0x prefix."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance._send_packet = AsyncMock(return_value=True)

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_RAW,
                {ATTR_DEVICE_ID: "device123", ATTR_COMMAND: "0x3E 0x1E"},
                blocking=True,
            )

            mock_instance._send_packet.assert_called_once_with([0x3E, 0x1E])

    @pytest.mark.asyncio
    async def test_send_raw_command_invalid_hex(self, hass: HomeAssistant) -> None:
        """Test send raw command with invalid hex."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance._send_packet = AsyncMock(return_value=True)

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            # Should not raise, but should not call _send_packet
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_RAW,
                {ATTR_DEVICE_ID: "device123", ATTR_COMMAND: "GG HH"},  # Invalid
                blocking=True,
            )

            mock_instance._send_packet.assert_not_called()


class TestSetTimerService:
    """Test set_timer service handler."""

    @pytest.mark.asyncio
    async def test_set_timer_success(self, hass: HomeAssistant) -> None:
        """Test set timer service success."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.set_timer = AsyncMock(return_value=True)

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_TIMER,
                {ATTR_DEVICE_ID: "device123", ATTR_MINUTES: 30},
                blocking=True,
            )

            mock_instance.set_timer.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_set_timer_failure(self, hass: HomeAssistant) -> None:
        """Test set timer service when timer fails."""
        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.set_timer = AsyncMock(return_value=False)

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            # Should not raise even on failure
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_TIMER,
                {ATTR_DEVICE_ID: "device123", ATTR_MINUTES: 30},
                blocking=True,
            )


class TestSunriseService:
    """Test start_sunrise service handler."""

    @pytest.mark.asyncio
    async def test_start_sunrise_defaults(self, hass: HomeAssistant) -> None:
        """Test start sunrise with default values."""
        mock_simulation = MagicMock()
        mock_simulation.start_sunrise = AsyncMock()

        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.sunrise_simulation = mock_simulation

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_SUNRISE,
                {ATTR_DEVICE_ID: "device123"},
                blocking=True,
            )

            mock_simulation.start_sunrise.assert_called_once_with(15, SunriseProfile.NATURAL)

    @pytest.mark.asyncio
    async def test_start_sunrise_custom(self, hass: HomeAssistant) -> None:
        """Test start sunrise with custom values."""
        mock_simulation = MagicMock()
        mock_simulation.start_sunrise = AsyncMock()

        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.sunrise_simulation = mock_simulation

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_SUNRISE,
                {
                    ATTR_DEVICE_ID: "device123",
                    ATTR_DURATION: 30,
                    ATTR_PROFILE: "therapy",
                },
                blocking=True,
            )

            mock_simulation.start_sunrise.assert_called_once_with(30, SunriseProfile.THERAPY)

    @pytest.mark.asyncio
    async def test_start_sunrise_all_profiles(self, hass: HomeAssistant) -> None:
        """Test start sunrise with all profile options."""
        profiles_map = {
            "gentle": SunriseProfile.GENTLE,
            "natural": SunriseProfile.NATURAL,
            "energize": SunriseProfile.ENERGIZE,
            "therapy": SunriseProfile.THERAPY,
        }

        from custom_components.beurer_daylight_lamps import _async_setup_services

        # Setup services once
        await _async_setup_services(hass)

        for profile_name, profile_enum in profiles_map.items():
            mock_simulation = MagicMock()
            mock_simulation.start_sunrise = AsyncMock()

            mock_instance = MagicMock()
            mock_instance.mac = "AA:BB:CC:DD:EE:FF"
            mock_instance.sunrise_simulation = mock_simulation

            with patch(
                "custom_components.beurer_daylight_lamps._get_instance_for_device",
                return_value=mock_instance,
            ):
                await hass.services.async_call(
                    DOMAIN,
                    SERVICE_START_SUNRISE,
                    {
                        ATTR_DEVICE_ID: "device123",
                        ATTR_PROFILE: profile_name,
                    },
                    blocking=True,
                )

                mock_simulation.start_sunrise.assert_called_with(15, profile_enum)


class TestSunsetService:
    """Test start_sunset service handler."""

    @pytest.mark.asyncio
    async def test_start_sunset_defaults(self, hass: HomeAssistant) -> None:
        """Test start sunset with default values."""
        mock_simulation = MagicMock()
        mock_simulation.start_sunset = AsyncMock()

        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.sunrise_simulation = mock_simulation

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_SUNSET,
                {ATTR_DEVICE_ID: "device123"},
                blocking=True,
            )

            mock_simulation.start_sunset.assert_called_once_with(30, 0)

    @pytest.mark.asyncio
    async def test_start_sunset_custom(self, hass: HomeAssistant) -> None:
        """Test start sunset with custom values."""
        mock_simulation = MagicMock()
        mock_simulation.start_sunset = AsyncMock()

        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.sunrise_simulation = mock_simulation

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_START_SUNSET,
                {
                    ATTR_DEVICE_ID: "device123",
                    ATTR_DURATION: 45,
                    ATTR_END_BRIGHTNESS: 20,
                },
                blocking=True,
            )

            mock_simulation.start_sunset.assert_called_once_with(45, 20)


class TestStopSimulationService:
    """Test stop_simulation service handler."""

    @pytest.mark.asyncio
    async def test_stop_simulation(self, hass: HomeAssistant) -> None:
        """Test stop simulation service."""
        mock_simulation = MagicMock()
        mock_simulation.stop = AsyncMock()

        mock_instance = MagicMock()
        mock_instance.mac = "AA:BB:CC:DD:EE:FF"
        mock_instance.sunrise_simulation = mock_simulation

        from custom_components.beurer_daylight_lamps import _async_setup_services

        with patch(
            "custom_components.beurer_daylight_lamps._get_instance_for_device",
            return_value=mock_instance,
        ):
            await _async_setup_services(hass)

            await hass.services.async_call(
                DOMAIN,
                SERVICE_STOP_SIMULATION,
                {ATTR_DEVICE_ID: "device123"},
                blocking=True,
            )

            mock_simulation.stop.assert_called_once()


# =============================================================================
# SERVICE REGISTRATION TESTS
# =============================================================================


class TestServiceRegistration:
    """Test service registration."""

    @pytest.mark.asyncio
    async def test_services_registered_once(self, hass: HomeAssistant) -> None:
        """Test services are only registered once."""
        from custom_components.beurer_daylight_lamps import _async_setup_services

        # Call setup twice
        await _async_setup_services(hass)
        await _async_setup_services(hass)

        # Verify all services are registered
        assert hass.services.has_service(DOMAIN, SERVICE_APPLY_PRESET)
        assert hass.services.has_service(DOMAIN, SERVICE_SEND_RAW)
        assert hass.services.has_service(DOMAIN, SERVICE_SET_TIMER)
        assert hass.services.has_service(DOMAIN, SERVICE_START_SUNRISE)
        assert hass.services.has_service(DOMAIN, SERVICE_START_SUNSET)
        assert hass.services.has_service(DOMAIN, SERVICE_STOP_SIMULATION)

    @pytest.mark.asyncio
    async def test_all_expected_services_registered(self, hass: HomeAssistant) -> None:
        """Test all expected services are registered."""
        from custom_components.beurer_daylight_lamps import _async_setup_services

        await _async_setup_services(hass)

        expected_services = [
            SERVICE_APPLY_PRESET,
            SERVICE_SEND_RAW,
            SERVICE_SET_TIMER,
            SERVICE_START_SUNRISE,
            SERVICE_START_SUNSET,
            SERVICE_STOP_SIMULATION,
        ]

        for service in expected_services:
            assert hass.services.has_service(DOMAIN, service), f"Service {service} not registered"
