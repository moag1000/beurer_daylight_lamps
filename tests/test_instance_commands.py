"""Settings, time sync, timer and turn on/off commands of BeurerInstance."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    CMD_SETTINGS_READ,
    CMD_SETTINGS_WRITE,
    CMD_TIME_SYNC,
    CMD_TIMER_CANCEL,
    CMD_TIMER_TOGGLE,
    CMD_TIMER_VALUE,
    CMD_WL75_LIGHT_TIMER_SWITCH,
    CMD_WL75_LIGHT_TIMER_VALUE,
    CMD_WL75_MOODLIGHT_TIMER_SWITCH,
    CMD_WL75_MOODLIGHT_TIMER_VALUE,
    CMD_WL75_SETTINGS_READ,
    CMD_WL75_SETTINGS_WRITE,
    CMD_WL75_TIME_SYNC,
    MODE_RGB,
    MODE_WHITE,
)

M = "custom_components.beurer_daylight_lamps.beurer_daylight_lamps"


@pytest.fixture(autouse=True)
def no_sleep():
    with patch(f"{M}.asyncio.sleep", new=AsyncMock()):
        yield


def make(name: str = "TL100", send_ok: bool = True) -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    inst = BeurerInstance(device)
    inst._send_packet = AsyncMock(return_value=send_ok)
    inst._trigger_update = AsyncMock()
    inst._request_status = AsyncMock()
    return inst


def sent(inst: BeurerInstance) -> list[list[int]]:
    return [c.args[0] for c in inst._send_packet.await_args_list]


NOW = datetime(2026, 11, 12, 7, 30, 15, tzinfo=UTC)  # a Thursday


class TestTimeAndSettings:
    """sync_time, query_settings, feedback and fade."""

    async def test_sync_time_tl(self) -> None:
        inst = make()
        with patch(f"{M}.dt_util.now", return_value=NOW):
            assert await inst.sync_time()
        assert sent(inst) == [[CMD_TIME_SYNC, 15, 30, 7, 4, 12, 11, 26]]
        assert inst.last_time_sync is not None

    async def test_sync_time_wl75(self) -> None:
        inst = make("WL75_1")
        with patch(f"{M}.dt_util.now", return_value=NOW):
            assert await inst.sync_time()
        assert sent(inst) == [[CMD_WL75_TIME_SYNC, 15, 30, 7, 12, 11, 26]]

    @pytest.mark.parametrize("name", ["TL100", "WL75_1"])
    async def test_sync_time_failure(self, name: str) -> None:
        inst = make(name, send_ok=False)
        assert not await inst.sync_time()
        assert inst.last_time_sync is None

    @pytest.mark.parametrize(
        ("name", "cmd", "ok"),
        [
            ("TL100", CMD_SETTINGS_READ, True),
            ("WL75_1", CMD_WL75_SETTINGS_READ, True),
            ("TL100", CMD_SETTINGS_READ, False),
        ],
    )
    async def test_query_settings(self, name: str, cmd: int, ok: bool) -> None:
        inst = make(name, send_ok=ok)
        assert await inst.query_settings() is ok
        assert sent(inst) == [[cmd]]

    async def test_feedback_tl_keeps_fade(self) -> None:
        inst = make()
        inst._fade_enabled = False
        assert await inst.set_feedback(True)
        assert sent(inst) == [[CMD_SETTINGS_WRITE, 0, 0, 0, 0, 1]]
        assert inst.feedback_enabled is True
        inst._trigger_update.assert_awaited_once()

    async def test_feedback_wl75(self) -> None:
        inst = make("WL75_1")
        inst._display_setting = 2
        assert await inst.set_feedback(False)
        assert sent(inst) == [[CMD_WL75_SETTINGS_WRITE, 2, 0, 0, 1]]
        assert inst.feedback_enabled is False

    @pytest.mark.parametrize("name", ["TL100", "WL75_1"])
    async def test_feedback_failure(self, name: str) -> None:
        inst = make(name, send_ok=False)
        assert not await inst.set_feedback(True)
        assert inst.feedback_enabled is None

    async def test_fade(self) -> None:
        inst = make()
        inst._feedback_enabled = False
        assert await inst.set_fade(True)
        assert sent(inst) == [[CMD_SETTINGS_WRITE, 0, 0, 0, 1, 0]]
        assert inst.fade_enabled is True
        failing = make(send_ok=False)
        assert not await failing.set_fade(False)
        assert failing.fade_enabled is None


class TestTimer:
    """set_timer and cancel_timer."""

    @pytest.mark.parametrize("minutes", [0, 121])
    async def test_out_of_range(self, minutes: int) -> None:
        inst = make()
        assert not await inst.set_timer(minutes)
        inst._send_packet.assert_not_awaited()

    @pytest.mark.parametrize(
        ("mode", "byte"), [(ColorMode.WHITE, MODE_WHITE), (ColorMode.RGB, MODE_RGB)]
    )
    async def test_tl(self, mode: ColorMode, byte: int) -> None:
        inst = make()
        inst._mode = mode
        assert await inst.set_timer(30)
        assert sent(inst) == [[CMD_TIMER_TOGGLE, byte], [CMD_TIMER_VALUE, byte, 30]]
        assert inst.timer_active
        assert inst.timer_minutes == 30
        assert await inst.cancel_timer()
        assert sent(inst)[-1] == [CMD_TIMER_CANCEL, byte]
        assert not inst.timer_active

    async def test_tl_failures(self) -> None:
        inst = make(send_ok=False)
        assert not await inst.set_timer(10)
        assert len(sent(inst)) == 1
        assert not await inst.cancel_timer()
        inst._send_packet = AsyncMock(side_effect=[True, False])
        assert not await inst.set_timer(10)
        assert not inst.timer_active

    @pytest.mark.parametrize(
        ("color_on", "switch", "value"),
        [
            (False, CMD_WL75_LIGHT_TIMER_SWITCH, CMD_WL75_LIGHT_TIMER_VALUE),
            (True, CMD_WL75_MOODLIGHT_TIMER_SWITCH, CMD_WL75_MOODLIGHT_TIMER_VALUE),
        ],
    )
    async def test_wl75(self, color_on: bool, switch: int, value: int) -> None:
        inst = make("WL75_1")
        inst._color_on = color_on
        assert await inst.set_timer(45)
        assert sent(inst) == [[switch, 1], [value, 45]]
        assert inst.timer_minutes == 45
        assert await inst.cancel_timer()
        assert sent(inst)[-1] == [switch, 0]
        assert inst.timer_minutes is None

    @pytest.mark.parametrize("color_on", [False, True])
    async def test_wl75_failures(self, color_on: bool) -> None:
        inst = make("WL75_1", send_ok=False)
        inst._color_on = color_on
        assert not await inst.set_timer(5)
        assert not await inst.cancel_timer()
        inst._send_packet = AsyncMock(side_effect=[True, False])
        assert not await inst.set_timer(5)
        assert not inst.timer_active


class TestTurnOn:
    """turn_on restores the previous state on the first turn-on."""

    def _prepare(self, inst: BeurerInstance, connected: bool = True) -> None:
        inst._client = MagicMock()
        inst._client.is_connected = connected
        inst._switch_to_mode = AsyncMock()
        inst.set_effect = AsyncMock()
        inst.set_color = AsyncMock()
        inst.set_color_brightness = AsyncMock()

    async def test_cannot_connect(self) -> None:
        inst = make()
        self._prepare(inst, connected=False)
        inst.connect = AsyncMock(return_value=False)
        await inst.turn_on()
        inst._switch_to_mode.assert_not_awaited()

    @pytest.mark.parametrize("name", ["TL100", "WL75_1"])
    async def test_white(self, name: str) -> None:
        inst = make(name)
        self._prepare(inst)
        await inst.turn_on()
        inst._switch_to_mode.assert_awaited_once_with(MODE_WHITE)
        assert inst._light_on
        assert inst._available
        inst._request_status.assert_awaited_once()

    @pytest.mark.parametrize("name", ["TL100", "WL75_1"])
    async def test_rgb_first_time_restores(self, name: str) -> None:
        inst = make(name)
        self._prepare(inst)
        inst._mode = ColorMode.RGB
        inst._effect = "Rainbow"
        inst._rgb_color = (1, 2, 3)
        inst._color_brightness = 100
        await inst.turn_on()
        inst._switch_to_mode.assert_awaited_once_with(MODE_RGB)
        inst.set_effect.assert_awaited_once_with("Rainbow", _from_turn_on=True)
        inst.set_color.assert_awaited_once_with((1, 2, 3), _from_turn_on=True)
        inst.set_color_brightness.assert_awaited_once_with(100, _from_turn_on=True)
        assert inst.color_on

    @pytest.mark.parametrize("name", ["TL100", "WL75_1"])
    async def test_rgb_black_without_brightness(self, name: str) -> None:
        inst = make(name)
        self._prepare(inst)
        inst._mode = ColorMode.RGB
        inst._rgb_color = (0, 0, 0)
        inst._color_brightness = None
        await inst.turn_on()
        inst.set_color.assert_not_awaited()
        inst.set_color_brightness.assert_not_awaited()

    @pytest.mark.parametrize("name", ["TL100", "WL75_1"])
    async def test_rgb_already_available(self, name: str) -> None:
        inst = make(name)
        self._prepare(inst)
        inst._mode = ColorMode.RGB
        inst._available = True
        await inst.turn_on()
        inst.set_effect.assert_not_awaited()
