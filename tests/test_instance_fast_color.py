"""set_color_with_brightness_fast (used by sunrise / sunset steps)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    CMD_BRIGHTNESS,
    CMD_COLOR,
    CMD_EFFECT,
    CMD_WL75_MOODLIGHT_BRIGHTNESS,
    CMD_WL75_MOODLIGHT_COLOR,
    CMD_WL75_MOODLIGHT_SCENE,
    MODE_RGB,
)

M = "custom_components.beurer_daylight_lamps.beurer_daylight_lamps"


@pytest.fixture(autouse=True)
def no_sleep():
    with patch(f"{M}.asyncio.sleep", new=AsyncMock()):
        yield


def make(name: str) -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    inst = BeurerInstance(device)
    inst._send_packet = AsyncMock(return_value=True)
    inst._switch_to_mode = AsyncMock()
    inst._trigger_update = AsyncMock()
    return inst


def packets(inst: BeurerInstance) -> list[list[int]]:
    return [c.args[0] for c in inst._send_packet.await_args_list]


@pytest.mark.parametrize(
    ("name", "effect_cmd", "color_cmd"),
    [
        ("TL100", [CMD_EFFECT, 0], CMD_COLOR),
        ("WL75_1", [CMD_WL75_MOODLIGHT_SCENE, 0], CMD_WL75_MOODLIGHT_COLOR),
    ],
)
async def test_first_step_switches_mode_and_clears_effect(
    name: str, effect_cmd: list[int], color_cmd: int
) -> None:
    inst = make(name)
    inst._effect = "Rainbow"
    await inst.set_color_with_brightness_fast((255.0, 100.4, 0), 128)
    inst._switch_to_mode.assert_awaited_once_with(MODE_RGB)
    sent = packets(inst)
    assert sent[0] == effect_cmd
    assert sent[1] == [color_cmd, 255, 100, 0]
    assert inst.color_mode == ColorMode.RGB
    assert inst.effect == "Off"
    assert inst.color_brightness == 128
    assert inst._mode_switch_target is None
    inst._trigger_update.assert_awaited_once()


async def test_tl_following_steps_skip_mode_switch() -> None:
    inst = make("TL100")
    inst._color_on = True
    await inst.set_color_with_brightness_fast((10, 20, 30), 255)
    inst._switch_to_mode.assert_not_awaited()
    assert packets(inst) == [[CMD_COLOR, 10, 20, 30], [CMD_BRIGHTNESS, MODE_RGB, 100]]


async def test_wl75_following_steps() -> None:
    inst = make("WL75_1")
    inst._color_on = True
    await inst.set_color_with_brightness_fast((10, 20, 30), 3)
    assert packets(inst) == [
        [CMD_WL75_MOODLIGHT_COLOR, 10, 20, 30],
        [CMD_WL75_MOODLIGHT_BRIGHTNESS, 1],
    ]
    await inst.set_color_with_brightness_fast((1, 2, 3))
    assert packets(inst)[-1] == [CMD_WL75_MOODLIGHT_COLOR, 1, 2, 3]
    assert inst._trigger_update.await_count == 2


async def test_mode_switch_error_resets_target() -> None:
    inst = make("TL100")
    inst._switch_to_mode = AsyncMock(side_effect=OSError("x"))
    with pytest.raises(OSError, match="x"):
        await inst.set_color_with_brightness_fast((1, 2, 3))
    assert inst._mode_switch_target is None
