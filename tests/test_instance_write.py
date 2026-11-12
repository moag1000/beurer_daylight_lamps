"""Low-level writes, packet retry, mode switch and WL75 color commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.exc import BleakError

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    CMD_BRIGHTNESS,
    CMD_COLOR,
    CMD_EFFECT,
    CMD_MODE,
    CMD_STATUS,
    CMD_WL75_LIGHT_STATUS,
    CMD_WL75_LIGHT_SWITCH,
    CMD_WL75_MOODLIGHT_BRIGHTNESS,
    CMD_WL75_MOODLIGHT_COLOR,
    CMD_WL75_MOODLIGHT_SCENE,
    CMD_WL75_MOODLIGHT_STATUS,
    CMD_WL75_MOODLIGHT_SWITCH,
    MODE_RGB,
    MODE_WHITE,
)

M = "custom_components.beurer_daylight_lamps.beurer_daylight_lamps"


@pytest.fixture(autouse=True)
def no_sleep():
    with patch(f"{M}.asyncio.sleep", new=AsyncMock()):
        yield


def make(name: str = "TL100") -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    return BeurerInstance(device)


def client(connected: bool = True) -> MagicMock:
    c = MagicMock()
    c.is_connected = connected
    c.write_gatt_char = AsyncMock()
    return c


class TestWrite:
    """_write."""

    async def test_reconnect_fails(self) -> None:
        inst = make()
        inst.connect = AsyncMock(return_value=False)
        assert not await inst._write(bytearray(b"\x01"))
        assert inst.command_success_rate == 0

    async def test_no_client_after_connect(self) -> None:
        inst = make()
        inst.connect = AsyncMock(return_value=True)
        assert not await inst._write(bytearray(b"\x01"))

    async def test_no_write_uuid(self) -> None:
        inst = make()
        inst._client = client()
        assert not await inst._write(bytearray(b"\x01"))

    async def test_success_marks_seen(self) -> None:
        inst = make()
        inst._client = client()
        inst._write_uuid = "w"
        inst._last_seen = 0
        assert await inst._write(bytearray(b"\x01"))
        assert inst._last_seen > 0
        assert inst.command_success_rate == 100

    @pytest.mark.parametrize("error", [TimeoutError(), BleakError("x"), OSError()])
    async def test_link_errors(self, error: Exception) -> None:
        inst = make()
        inst._client = client()
        inst._client.write_gatt_char = AsyncMock(side_effect=error)
        inst._write_uuid = "w"
        inst.disconnect = AsyncMock()
        assert not await inst._write(bytearray(b"\x01"))
        assert inst._last_write_link_error
        inst.disconnect.assert_awaited_once()


class TestSendPacket:
    """_send_packet framing and retry."""

    async def test_not_connected(self) -> None:
        inst = make()
        inst.connect = AsyncMock(return_value=False)
        assert not await inst._send_packet([0x30])

    async def test_retry_after_link_error(self) -> None:
        inst = make()
        inst._client = client()

        async def write(_packet: bytearray) -> bool:
            if inst._write.await_count == 1:
                inst._last_write_link_error = True
                return False
            return True

        inst._write = AsyncMock(side_effect=write)
        assert await inst._send_packet([0x30])
        assert inst._write.await_count == 2

    async def test_no_retry_while_closing(self) -> None:
        inst = make()
        inst._client = client()
        inst._closing = True

        async def write(_packet: bytearray) -> bool:
            inst._last_write_link_error = True
            return False

        inst._write = AsyncMock(side_effect=write)
        assert not await inst._send_packet([0x30])
        assert inst._write.await_count == 1


def recorder(inst: BeurerInstance) -> None:
    inst._send_packet = AsyncMock(return_value=True)
    inst._request_status = AsyncMock()
    inst._trigger_update = AsyncMock()


def sent(inst: BeurerInstance) -> list[list[int]]:
    return [c.args[0] for c in inst._send_packet.await_args_list]


class TestSwitchToMode:
    """Mode switch sequences."""

    async def test_tl(self) -> None:
        inst = make()
        recorder(inst)
        await inst._switch_to_mode(MODE_RGB)
        assert sent(inst) == [[CMD_MODE, MODE_RGB], [CMD_STATUS, MODE_RGB]]

    async def test_wl75_white(self) -> None:
        inst = make("WL75_1")
        recorder(inst)
        await inst._switch_to_mode(MODE_WHITE)
        assert sent(inst) == [
            [CMD_WL75_MOODLIGHT_SWITCH, 0],
            [CMD_WL75_LIGHT_SWITCH, 1],
            [CMD_WL75_LIGHT_STATUS],
        ]

    async def test_wl75_rgb(self) -> None:
        inst = make("WL75_1")
        recorder(inst)
        await inst._switch_to_mode(MODE_RGB)
        assert sent(inst) == [
            [CMD_WL75_LIGHT_SWITCH, 0],
            [CMD_WL75_MOODLIGHT_SWITCH, 1],
            [CMD_WL75_MOODLIGHT_STATUS],
        ]


class TestColorCommands:
    """set_color, set_color_with_brightness, set_color_brightness."""

    async def test_tl_set_color_clears_effect(self) -> None:
        inst = make()
        recorder(inst)
        inst._switch_to_mode = AsyncMock()
        inst._effect = "Rainbow"
        await inst.set_color((1, 2, 3))
        assert sent(inst) == [[CMD_EFFECT, 0], [CMD_COLOR, 1, 2, 3]]
        assert inst.color_on
        assert inst._mode_switch_target is None

    async def test_wl75_set_color(self) -> None:
        inst = make("WL75_1")
        recorder(inst)
        inst._switch_to_mode = AsyncMock()
        await inst.set_color((1, 2, 3))
        inst._switch_to_mode.assert_awaited_once_with(MODE_RGB)
        assert sent(inst) == [
            [CMD_WL75_MOODLIGHT_SCENE, 0],
            [CMD_WL75_MOODLIGHT_COLOR, 1, 2, 3],
        ]
        inst._switch_to_mode.reset_mock()
        await inst.set_color((4, 5, 6))
        inst._switch_to_mode.assert_not_awaited()

    @pytest.mark.parametrize(
        ("brightness", "stored", "percent"),
        [(128, None, 50), (None, 51, 20), (None, None, 100)],
    )
    async def test_wl75_color_with_brightness(
        self, brightness: int | None, stored: int | None, percent: int
    ) -> None:
        inst = make("WL75_1")
        recorder(inst)
        inst._switch_to_mode = AsyncMock()
        inst._color_brightness = stored
        await inst.set_color_with_brightness((9, 8, 7), brightness)
        assert sent(inst)[-1] == [CMD_WL75_MOODLIGHT_BRIGHTNESS, percent]
        assert inst.color_on

    async def test_tl_color_with_brightness_switches_mode(self) -> None:
        inst = make()
        recorder(inst)
        inst._switch_to_mode = AsyncMock()
        await inst.set_color_with_brightness((9, 8, 7))
        inst._switch_to_mode.assert_awaited_once_with(MODE_RGB)
        assert sent(inst) == [[CMD_COLOR, 9, 8, 7]]

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("TL100", [CMD_BRIGHTNESS, MODE_RGB, 100]),
            ("WL75_1", [CMD_WL75_MOODLIGHT_BRIGHTNESS, 100]),
        ],
    )
    async def test_color_brightness_switches_mode(
        self, name: str, expected: list[int]
    ) -> None:
        inst = make(name)
        recorder(inst)
        inst._switch_to_mode = AsyncMock()
        await inst.set_color_brightness(None)
        inst._switch_to_mode.assert_awaited_once_with(MODE_RGB)
        assert sent(inst) == [expected]
        assert inst.color_on
        assert inst.color_brightness == 255
