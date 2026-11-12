"""More WL75 (protocol 2) notification handling in BeurerInstance."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.light import ColorMode
import pytest

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    EVENT_TYPE_SLEEP_TIMER_FINISHED,
    EVENT_TYPE_TIMER_FINISHED,
    RESP_WL75_LIGHT_STATUS,
    RESP_WL75_LIGHT_SWITCH,
    RESP_WL75_MOODLIGHT_STATUS,
    RESP_WL75_PERMISSION,
    RESP_WL75_RADIO_POWER,
    RESP_WL75_SETTINGS,
    RESP_WL75_TIMER_END,
    RESP_WL75_UPDATE_TIME,
)


def _frame(payload: list[int]) -> bytearray:
    plen = len(payload) + 1
    checksum = plen
    for byte in payload:
        checksum ^= byte
    return bytearray([0xFE, 0xEF, plen, *payload, checksum])


@pytest.fixture
def inst() -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "WL75_1234"
    instance = BeurerInstance(device)
    instance._trigger_update = AsyncMock()
    instance.emit_lamp_event = MagicMock()
    return instance


@pytest.mark.parametrize(
    "data",
    [
        bytearray([0xFE, 0xEF]),
        bytearray([0x00, 0xEF, 0x02, 0x01, 0x03]),
        bytearray([0xFE, 0xEF, 0x09, 0x01]),
        bytearray([0xFE, 0xEF, 0x01, 0x01]),  # empty payload
    ],
)
async def test_invalid_frames_ignored(inst: BeurerInstance, data: bytearray) -> None:
    await inst._handle_wl75_notification(data)
    inst._trigger_update.assert_not_awaited()
    assert inst.heartbeat_count == 0


async def test_white_status_off_with_timer(inst: BeurerInstance) -> None:
    inst._light_on = True
    await inst._handle_wl75_notification(
        _frame([RESP_WL75_LIGHT_STATUS, 0, 150, 1, 20])
    )
    assert not inst._light_on
    assert inst._white_brightness == 255
    assert inst.white_brightness is None  # only reported while the light is on
    assert inst.timer_active
    assert inst.timer_minutes == 20
    assert inst._available


async def test_white_status_short_payload(inst: BeurerInstance) -> None:
    await inst._handle_wl75_notification(_frame([RESP_WL75_LIGHT_STATUS, 1]))
    inst._trigger_update.assert_not_awaited()


async def test_moodlight_full_brightness_and_unknown_scene(
    inst: BeurerInstance,
) -> None:
    await inst._handle_wl75_notification(
        _frame([RESP_WL75_MOODLIGHT_STATUS, 0xFF, 10, 0, 0, 1, 2, 3, 99])
    )
    assert inst.color_on
    assert inst.color_mode == ColorMode.RGB
    assert inst.color_brightness == 255
    assert inst.rgb_color == (1, 2, 3)
    assert inst.effect == "Off"
    assert not inst.timer_active
    assert inst.timer_minutes is None


async def test_moodlight_off(inst: BeurerInstance) -> None:
    inst._color_on = True
    await inst._handle_wl75_notification(
        _frame([RESP_WL75_MOODLIGHT_STATUS, 0, 50, 1, 5, 1, 2, 3, 1])
    )
    assert not inst.color_on
    assert inst.timer_minutes == 5
    await inst._handle_wl75_notification(_frame([RESP_WL75_MOODLIGHT_STATUS, 1]))
    assert inst._trigger_update.await_count == 1


@pytest.mark.parametrize(("kind", "name"), [(2, "light"), (3, "moonlight")])
async def test_light_timer_end(inst: BeurerInstance, kind: int, name: str) -> None:
    inst._light_on = True
    inst._timer_active = True
    await inst._handle_wl75_notification(_frame([RESP_WL75_TIMER_END, kind]))
    assert not inst._light_on
    assert not inst.timer_active
    inst.emit_lamp_event.assert_called_once_with(
        EVENT_TYPE_TIMER_FINISHED, {"timer": name}
    )


async def test_radio_timer_end(inst: BeurerInstance) -> None:
    inst.wl90.radio.sleep_timer_on = True
    await inst._handle_wl75_notification(_frame([RESP_WL75_TIMER_END, 1]))
    assert not inst.wl90.radio.sleep_timer_on
    inst.emit_lamp_event.assert_called_once_with(
        EVENT_TYPE_SLEEP_TIMER_FINISHED, {"timer": "radio"}
    )
    await inst._handle_wl75_notification(_frame([RESP_WL75_TIMER_END]))
    assert inst._trigger_update.await_count == 2


async def test_permission(inst: BeurerInstance) -> None:
    await inst._handle_wl75_notification(_frame([RESP_WL75_PERMISSION, 0x75]))
    assert inst._device_permission_granted
    await inst._handle_wl75_notification(_frame([RESP_WL75_PERMISSION, 0x00]))
    assert not inst._device_permission_granted


async def test_settings(inst: BeurerInstance) -> None:
    await inst._handle_wl75_notification(_frame([RESP_WL75_SETTINGS, 1, 2, 3, 0]))
    assert inst._display_setting == 1
    assert inst._date_format == 2
    assert inst._time_format == 3
    assert inst.feedback_enabled is True
    await inst._handle_wl75_notification(_frame([RESP_WL75_SETTINGS, 1]))
    assert inst._trigger_update.await_count == 1


async def test_controller_response_makes_available(inst: BeurerInstance) -> None:
    await inst._handle_wl75_notification(_frame([RESP_WL75_RADIO_POWER]))
    assert inst._available
    inst._trigger_update.assert_awaited_once()


@pytest.mark.parametrize("resp", [RESP_WL75_LIGHT_SWITCH, RESP_WL75_UPDATE_TIME, 0x42])
async def test_acks_and_unknown(inst: BeurerInstance, resp: int) -> None:
    await inst._handle_wl75_notification(_frame([resp]))
    inst._trigger_update.assert_not_awaited()
    assert inst.heartbeat_count == 1
