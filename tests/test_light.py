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


def test_light_properties() -> None:
    """Test light entity properties."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.is_on = True
    mock_instance.rgb_color = (255, 128, 64)
    mock_instance.color_brightness = 200
    mock_instance.white_brightness = 255
    mock_instance.effect = "Rainbow"
    mock_instance.color_mode = ColorMode.RGB
    mock_instance.supported_effects = ["Off", "Rainbow"]

    light = BeurerLight(mock_instance, "Test TL100", "entry_id")

    # Unique ID is normalized MAC address
    assert light.unique_id == "aa:bb:cc:dd:ee:ff"
    assert light.is_on is True
    assert light.effect == "Rainbow"
    assert light.effect_list == ["Off", "Rainbow"]
    assert light.color_mode == ColorMode.RGB


def test_light_brightness_white_mode() -> None:
    """Test brightness in white mode."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.color_mode = ColorMode.WHITE
    mock_instance.white_brightness = 128
    mock_instance.color_brightness = 255

    light = BeurerLight(mock_instance, "Test", "entry_id")

    assert light.brightness == 128


def test_light_brightness_rgb_mode() -> None:
    """Test brightness in RGB mode."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.color_mode = ColorMode.RGB
    mock_instance.white_brightness = 128
    mock_instance.color_brightness = 200

    light = BeurerLight(mock_instance, "Test", "entry_id")

    assert light.brightness == 200


def test_light_available() -> None:
    """Test availability based on connection state (not power state)."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"

    light = BeurerLight(mock_instance, "Test", "entry_id")

    # Available when connected (regardless of power state)
    mock_instance.available = True
    assert light.available is True

    # Unavailable when disconnected
    mock_instance.available = False
    assert light.available is False


def test_light_device_info() -> None:
    """Test device info generation."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"

    light = BeurerLight(mock_instance, "TL100", "entry_id")
    device_info = light.device_info

    assert device_info["manufacturer"] == "Beurer"
    assert device_info["model"] == "TL100 Daylight Therapy Lamp"
    assert device_info["name"] == "TL100"


@pytest.mark.asyncio
async def test_turn_on_no_params() -> None:
    """Test turn on without parameters."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.turn_on = AsyncMock()

    light = BeurerLight(mock_instance, "Test", "entry_id")
    await light.async_turn_on()

    mock_instance.turn_on.assert_called_once()


@pytest.mark.asyncio
async def test_turn_on_with_brightness() -> None:
    """Test turn on with brightness (white mode)."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.set_white = AsyncMock()
    mock_instance.set_color_brightness = AsyncMock()
    mock_instance.color_mode = ColorMode.WHITE
    mock_instance._color_on = False

    light = BeurerLight(mock_instance, "Test", "entry_id")
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 128})

    mock_instance.set_white.assert_called_once_with(128)


@pytest.mark.asyncio
async def test_turn_on_with_rgb() -> None:
    """Test turn on with RGB color."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.set_color_with_brightness = AsyncMock()
    mock_instance.color_brightness = None  # No current brightness
    mock_instance._mode = ColorMode.WHITE

    light = BeurerLight(mock_instance, "Test", "entry_id")
    await light.async_turn_on(**{ATTR_RGB_COLOR: (255, 128, 64)})

    mock_instance.set_color_with_brightness.assert_called_once_with((255, 128, 64), None)


@pytest.mark.asyncio
async def test_turn_on_with_effect() -> None:
    """Test turn on with effect."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.set_effect = AsyncMock()
    mock_instance._mode = ColorMode.WHITE

    light = BeurerLight(mock_instance, "Test", "entry_id")
    await light.async_turn_on(**{ATTR_EFFECT: "Rainbow"})

    mock_instance.set_effect.assert_called_once_with("Rainbow")


@pytest.mark.asyncio
async def test_turn_off() -> None:
    """Test turn off."""
    mock_instance = MagicMock()
    mock_instance.mac = "AA:BB:CC:DD:EE:FF"
    mock_instance.turn_off = AsyncMock()

    light = BeurerLight(mock_instance, "Test", "entry_id")
    await light.async_turn_off()

    mock_instance.turn_off.assert_called_once()
