"""Test Beurer Daylight Lamps light entity."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
)
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.const import detect_model
from custom_components.beurer_daylight_lamps.light import BeurerLight
from tests.conftest import create_mock_coordinator


def test_detect_model_tl100() -> None:
    """Test model detection for TL100."""
    assert detect_model("TL100") == "TL100 Daylight Therapy Lamp"
    assert detect_model("tl100") == "TL100 Daylight Therapy Lamp"
    assert detect_model("TL100-ABC") == "TL100 Daylight Therapy Lamp"


def test_detect_model_other() -> None:
    """Test model detection for other models."""
    assert detect_model("TL50") == "TL50 Daylight Therapy Lamp"
    assert detect_model("TL70") == "TL70 Daylight Therapy Lamp"
    assert detect_model("TL80") == "TL80 Daylight Therapy Lamp"
    assert detect_model("TL90") == "TL90 Daylight Therapy Lamp"


def test_detect_model_unknown() -> None:
    """Test model detection for unknown device."""
    assert detect_model("Unknown") == "Daylight Therapy Lamp"
    assert detect_model(None) == "Daylight Therapy Lamp"
    assert detect_model("") == "Daylight Therapy Lamp"


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock BeurerInstance."""
    instance = MagicMock()
    instance.mac = "AA:BB:CC:DD:EE:FF"
    instance.is_on = True
    instance.rgb_color = (255, 128, 64)
    instance.color_brightness = 200
    instance.white_brightness = 255
    instance.effect = "Rainbow"
    instance.color_mode = ColorMode.RGB
    instance.supported_effects = ["Off", "Rainbow"]
    instance.available = True
    instance.set_update_callback = MagicMock()
    instance.remove_update_callback = MagicMock()
    instance.update = AsyncMock()
    instance.turn_on = AsyncMock()
    instance.turn_off = AsyncMock()
    instance.set_white = AsyncMock()
    instance.set_color_brightness = AsyncMock()
    instance.set_color_with_brightness = AsyncMock()
    instance.set_effect = AsyncMock()
    instance.color_on = False
    return instance


@pytest.fixture
def mock_coordinator(mock_instance: MagicMock) -> MagicMock:
    """Create a mock coordinator."""
    return create_mock_coordinator(mock_instance)


def test_light_properties(mock_coordinator: MagicMock) -> None:
    """Test light entity properties."""
    light = BeurerLight(mock_coordinator, "Test TL100", "entry_id")

    # Unique ID is normalized MAC address
    assert light.unique_id == "aa:bb:cc:dd:ee:ff"
    assert light.is_on is True
    assert light.effect == "Rainbow"
    assert light.effect_list == ["Off", "Rainbow"]
    assert light.color_mode == ColorMode.RGB


def test_light_instance_reference(mock_coordinator: MagicMock) -> None:
    """Test light correctly references instance from coordinator."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    assert light._instance == mock_coordinator.instance


def test_light_brightness_white_mode(mock_coordinator: MagicMock) -> None:
    """Test brightness in white mode."""
    mock_coordinator.instance.color_mode = ColorMode.WHITE
    mock_coordinator.instance.white_brightness = 128
    mock_coordinator.instance.color_brightness = 255

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    assert light.brightness == 128


def test_light_brightness_rgb_mode(mock_coordinator: MagicMock) -> None:
    """Test brightness in RGB mode."""
    mock_coordinator.instance.color_mode = ColorMode.RGB
    mock_coordinator.instance.white_brightness = 128
    mock_coordinator.instance.color_brightness = 200

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    assert light.brightness == 200


def test_light_available(mock_coordinator: MagicMock) -> None:
    """Test availability based on connection state (not power state)."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    # Available when connected (regardless of power state)
    mock_coordinator.instance.available = True
    assert light.available is True

    # Unavailable when disconnected
    mock_coordinator.instance.available = False
    assert light.available is False


def test_light_device_info(mock_coordinator: MagicMock) -> None:
    """Test device info generation."""
    light = BeurerLight(mock_coordinator, "TL100", "entry_id")
    device_info = light.device_info

    assert device_info["manufacturer"] == "Beurer"
    assert device_info["model"] == "TL100 Daylight Therapy Lamp"
    assert device_info["name"] == "TL100"


@pytest.mark.asyncio
async def test_turn_on_no_params(mock_coordinator: MagicMock) -> None:
    """Test turn on without parameters."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    await light.async_turn_on()

    mock_coordinator.instance.turn_on.assert_called_once()


@pytest.mark.asyncio
async def test_turn_on_with_brightness(mock_coordinator: MagicMock) -> None:
    """Test turn on with brightness (white mode)."""
    mock_coordinator.instance.color_mode = ColorMode.WHITE
    mock_coordinator.instance.color_on = False

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 128})

    mock_coordinator.instance.set_white.assert_called_once_with(128)


@pytest.mark.asyncio
async def test_turn_on_with_rgb(mock_coordinator: MagicMock) -> None:
    """Test turn on with RGB color."""
    mock_coordinator.instance.color_brightness = None
    mock_coordinator.instance._mode = ColorMode.WHITE

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    await light.async_turn_on(**{ATTR_RGB_COLOR: (255, 128, 64)})

    mock_coordinator.instance.set_color_with_brightness.assert_called_once_with((255, 128, 64), None)


@pytest.mark.asyncio
async def test_turn_on_with_effect(mock_coordinator: MagicMock) -> None:
    """Test turn on with effect."""
    mock_coordinator.instance._mode = ColorMode.WHITE

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    await light.async_turn_on(**{ATTR_EFFECT: "Rainbow"})

    mock_coordinator.instance.set_effect.assert_called_once_with("Rainbow")


@pytest.mark.asyncio
async def test_turn_off(mock_coordinator: MagicMock) -> None:
    """Test turn off."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    await light.async_turn_off()

    mock_coordinator.instance.turn_off.assert_called_once()


# =============================================================================
# Additional Tests for Full Coverage
# =============================================================================


@pytest.mark.asyncio
async def test_async_added_to_hass(mock_coordinator: MagicMock) -> None:
    """Test callback is registered when added to hass."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    await light.async_added_to_hass()

    mock_coordinator.instance.update.assert_called_once()


def test_should_poll_false(mock_coordinator: MagicMock) -> None:
    """Test should_poll is False (uses BLE notifications)."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    assert light.should_poll is False


def test_rgb_color_with_value(mock_coordinator: MagicMock) -> None:
    """Test rgb_color returns scaled value."""
    mock_coordinator.instance.rgb_color = (200, 100, 50)

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    result = light.rgb_color
    assert result is not None
    # match_max_scale scales to max 255
    assert max(result) == 255


def test_rgb_color_none(mock_coordinator: MagicMock) -> None:
    """Test rgb_color returns None when no color set."""
    mock_coordinator.instance.rgb_color = None

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    assert light.rgb_color is None


def test_color_temp_kelvin_in_color_temp_mode(mock_coordinator: MagicMock) -> None:
    """Test color_temp_kelvin returns value in COLOR_TEMP mode."""
    mock_coordinator.instance.color_mode = ColorMode.COLOR_TEMP

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    light._color_temp_kelvin = 4000

    assert light.color_temp_kelvin == 4000


def test_color_temp_kelvin_not_in_color_temp_mode(mock_coordinator: MagicMock) -> None:
    """Test color_temp_kelvin returns None when not in COLOR_TEMP mode."""
    mock_coordinator.instance.color_mode = ColorMode.RGB

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    light._color_temp_kelvin = 4000

    assert light.color_temp_kelvin is None


def test_effect_in_white_mode(mock_coordinator: MagicMock) -> None:
    """Test effect returns None in white mode."""
    mock_coordinator.instance.color_mode = ColorMode.WHITE
    mock_coordinator.instance.effect = "Rainbow"

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    assert light.effect is None


def test_color_mode_white(mock_coordinator: MagicMock) -> None:
    """Test color_mode returns WHITE when in native white mode."""
    mock_coordinator.instance.color_mode = ColorMode.WHITE

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    assert light.color_mode == ColorMode.WHITE


def test_color_mode_color_temp(mock_coordinator: MagicMock) -> None:
    """Test color_mode returns COLOR_TEMP when tracking color temp."""
    mock_coordinator.instance.color_mode = ColorMode.RGB

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    light._color_temp_kelvin = 4000

    assert light.color_mode == ColorMode.COLOR_TEMP


@pytest.mark.asyncio
async def test_turn_on_white_rgb_from_homekit(mock_coordinator: MagicMock) -> None:
    """Test turn on with white-ish RGB from HomeKit triggers white mode."""
    mock_coordinator.instance.white_brightness = 200

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    # White RGB values (all high and similar)
    await light.async_turn_on(**{ATTR_RGB_COLOR: (255, 255, 255)})

    mock_coordinator.instance.set_white.assert_called_once()
    mock_coordinator.instance.set_color_with_brightness.assert_not_called()


@pytest.mark.asyncio
async def test_turn_on_near_white_rgb_from_homekit(mock_coordinator: MagicMock) -> None:
    """Test turn on with near-white RGB from HomeKit triggers white mode."""
    mock_coordinator.instance.white_brightness = 200

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    # Near-white RGB values (all >= 200 and within 55 of each other)
    await light.async_turn_on(**{ATTR_RGB_COLOR: (220, 230, 225)})

    mock_coordinator.instance.set_white.assert_called_once()


@pytest.mark.asyncio
async def test_turn_on_color_temp_high_kelvin(mock_coordinator: MagicMock) -> None:
    """Test turn on with high color temp uses native white mode."""
    from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN

    mock_coordinator.instance.white_brightness = 200

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    # High kelvin >= WHITE_MODE_THRESHOLD_KELVIN (5000K)
    await light.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 5500})

    mock_coordinator.instance.set_white.assert_called_once()
    assert light._color_temp_kelvin == 5500


@pytest.mark.asyncio
async def test_turn_on_color_temp_low_kelvin(mock_coordinator: MagicMock) -> None:
    """Test turn on with low color temp simulates via RGB."""
    from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN

    mock_coordinator.instance.color_brightness = 200

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    # Low kelvin < WHITE_MODE_THRESHOLD_KELVIN (5000K)
    await light.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 3000})

    mock_coordinator.instance.set_color_with_brightness.assert_called_once()
    assert light._color_temp_kelvin == 3000


@pytest.mark.asyncio
async def test_turn_on_color_temp_with_brightness(mock_coordinator: MagicMock) -> None:
    """Test turn on with color temp and brightness."""
    from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN

    mock_coordinator.instance.color_brightness = 100

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    await light.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 3000, ATTR_BRIGHTNESS: 180})

    mock_coordinator.instance.set_color_with_brightness.assert_called_once()
    call_args = mock_coordinator.instance.set_color_with_brightness.call_args
    assert call_args[0][1] == 180


@pytest.mark.asyncio
async def test_turn_on_with_effect_and_brightness(mock_coordinator: MagicMock) -> None:
    """Test turn on with effect and brightness."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    await light.async_turn_on(**{ATTR_EFFECT: "Rainbow", ATTR_BRIGHTNESS: 200})

    mock_coordinator.instance.set_effect.assert_called_once_with("Rainbow")
    mock_coordinator.instance.set_color_brightness.assert_called_once_with(200)


@pytest.mark.asyncio
async def test_turn_on_brightness_only_color_temp_mode(mock_coordinator: MagicMock) -> None:
    """Test brightness only when in color temp mode."""
    mock_coordinator.instance.color_mode = ColorMode.RGB

    light = BeurerLight(mock_coordinator, "Test", "entry_id")
    light._color_temp_kelvin = 4000  # In color temp mode

    await light.async_turn_on(**{ATTR_BRIGHTNESS: 200})

    mock_coordinator.instance.set_color_brightness.assert_called_once_with(200)


@pytest.mark.asyncio
async def test_turn_on_brightness_only_rgb_mode(mock_coordinator: MagicMock) -> None:
    """Test brightness only when in RGB mode."""
    mock_coordinator.instance.color_mode = ColorMode.RGB
    mock_coordinator.instance.color_on = True

    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    await light.async_turn_on(**{ATTR_BRIGHTNESS: 200})

    mock_coordinator.instance.set_color_brightness.assert_called_once_with(200)


@pytest.mark.asyncio
async def test_async_update(mock_coordinator: MagicMock) -> None:
    """Test async_update fetches new state."""
    light = BeurerLight(mock_coordinator, "Test", "entry_id")

    await light.async_update()

    mock_coordinator.instance.update.assert_called_once()


# =============================================================================
# Test async_setup_entry
# =============================================================================


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.fixture
    def mock_instance(self) -> MagicMock:
        """Create a mock BeurerInstance."""
        instance = MagicMock()
        instance.mac = "AA:BB:CC:DD:EE:FF"
        return instance

    @pytest.fixture
    def mock_coordinator(self, mock_instance: MagicMock) -> MagicMock:
        """Create a mock coordinator."""
        return create_mock_coordinator(mock_instance)

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_light(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry creates a light entity."""
        from custom_components.beurer_daylight_lamps.light import async_setup_entry

        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {"name": "Test Lamp"}
        mock_entry.entry_id = "entry_123"

        mock_hass = MagicMock()
        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        assert len(added_entities) == 1
        assert isinstance(added_entities[0], BeurerLight)
        assert added_entities[0]._device_name == "Test Lamp"

    @pytest.mark.asyncio
    async def test_async_setup_entry_default_name(self, mock_coordinator: MagicMock) -> None:
        """Test that async_setup_entry uses default name when not provided."""
        from custom_components.beurer_daylight_lamps.light import async_setup_entry

        mock_runtime_data = MagicMock()
        mock_runtime_data.coordinator = mock_coordinator

        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_runtime_data
        mock_entry.data = {}  # No name provided
        mock_entry.entry_id = "entry_123"

        mock_hass = MagicMock()
        added_entities = []

        await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

        assert added_entities[0]._device_name == "Beurer Lamp"
