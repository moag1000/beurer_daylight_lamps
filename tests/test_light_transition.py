"""Tests for software transitions on the light entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.light import ColorMode, LightEntityFeature

from custom_components.beurer_daylight_lamps.light import BeurerLight
from tests.conftest import create_mock_coordinator


@pytest.fixture
def instance() -> MagicMock:
    """A lamp in native white that remembers what it was told."""
    inst = MagicMock()
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst.is_on = True
    inst.color_mode = ColorMode.WHITE
    inst.white_brightness = 200
    inst.color_brightness = 200
    inst.color_on = False

    async def set_white(value):
        inst.white_brightness = value
        inst.is_on = True

    async def turn_off():
        inst.is_on = False

    inst.set_white = AsyncMock(side_effect=set_white)
    inst.turn_off = AsyncMock(side_effect=turn_off)
    inst.turn_on = AsyncMock()
    inst.set_color_brightness = AsyncMock()
    inst.set_color_with_brightness = AsyncMock()
    inst.set_effect = AsyncMock()
    return inst


@pytest.fixture
def light(hass, instance) -> BeurerLight:
    entity = BeurerLight(create_mock_coordinator(instance), "Test TL100", "entry")
    entity.hass = hass
    return entity


def test_transition_supported(light) -> None:
    """The light announces transition support."""
    assert light.supported_features & LightEntityFeature.TRANSITION


async def test_fade_brightness(hass, light, instance) -> None:
    """A transition steps the brightness up to the target."""
    await light.async_turn_on(brightness=250, transition=2)
    await hass.async_block_till_done(wait_background_tasks=True)

    values = [c.args[0] for c in instance.set_white.call_args_list]
    assert values[0] == 200  # starts at the current brightness
    assert values[-1] == 250
    assert values == sorted(values)
    assert len(values) > 2


async def test_fade_on_from_off(hass, light, instance) -> None:
    """Turning on with a transition starts dim and ends at the target."""
    instance.is_on = False
    await light.async_turn_on(brightness=100, transition=1)
    await hass.async_block_till_done(wait_background_tasks=True)

    values = [c.args[0] for c in instance.set_white.call_args_list]
    assert values[0] == 1
    assert values[-1] == 100


async def test_fade_off_and_restore(hass, light, instance) -> None:
    """Fading out turns off, the next turn_on restores the old brightness."""
    await light.async_turn_off(transition=1)
    await hass.async_block_till_done(wait_background_tasks=True)

    instance.turn_off.assert_awaited_once()
    assert instance.white_brightness == 1  # dim end of the fade

    instance.set_white.reset_mock()
    await light.async_turn_on()
    instance.set_white.assert_awaited_once_with(200)


async def test_new_command_cancels_fade(hass, light, instance) -> None:
    """A command during a fade stops it."""
    await light.async_turn_on(brightness=10, transition=30)
    await light.async_turn_off()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert light._fade_task is None
    assert instance.is_on is False
    # nothing after the turn_off
    assert instance.set_white.await_count <= 1


async def test_no_transition_is_unchanged(hass, light, instance) -> None:
    """Without transition the command is sent directly."""
    await light.async_turn_on(brightness=120)
    instance.set_white.assert_awaited_once_with(120)
    await light.async_turn_off()
    instance.turn_off.assert_awaited_once()
