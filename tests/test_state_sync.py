"""Regression tests: state sync, command serialization and connection handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode

from custom_components.beurer_daylight_lamps import beurer_daylight_lamps as lib
from custom_components.beurer_daylight_lamps.const import (
    CMD_BRIGHTNESS,
    CMD_EFFECT,
    CMD_MODE,
    CMD_STATUS,
    MODE_RGB,
    MODE_WHITE,
)
from custom_components.beurer_daylight_lamps.coordinator import (
    BeurerDataUpdateCoordinator,
)

_real_sleep = asyncio.sleep


async def _no_wait(_delay: float) -> None:
    """Yield to the loop without waiting, so interleaving can happen."""
    await _real_sleep(0)


@pytest.fixture
def instance() -> lib.BeurerInstance:
    """Connected instance whose packets are recorded instead of sent."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "TL100"
    inst = lib.BeurerInstance(device)
    inst._client = MagicMock()
    inst._client.is_connected = True
    inst._write_uuid = "test-uuid"
    inst.sent = []

    async def record(packet: list[int]) -> bool:
        inst.sent.append(list(packet))
        await _real_sleep(0)
        return True

    inst._send_packet = record
    return inst


@pytest.mark.parametrize(
    ("method", "args", "color_on", "light_on"),
    [
        ("set_effect", ("Rainbow",), True, False),
        ("set_color", ((255, 0, 0),), True, False),
        ("set_color_with_brightness", ((255, 0, 0), 128), True, False),
        ("set_color_with_brightness_fast", ((255, 0, 0), 128), True, False),
        ("set_color_brightness", (200,), True, False),
        ("set_white", (200,), False, True),
        ("set_timer", (30,), False, True),
        ("cancel_timer", (), False, True),
    ],
)
async def test_command_in_current_mode_pushes_state(
    instance: lib.BeurerInstance,
    method: str,
    args: tuple,
    color_on: bool,
    light_on: bool,
) -> None:
    """A command without a mode switch must still refresh the entity.

    The lamp's confirming status equals the optimistic state, so it is not a
    change; without an explicit push the entity stays stale until the poll.
    """
    instance._color_on = color_on
    instance._light_on = light_on
    callback = MagicMock()
    instance.set_update_callback(callback)

    with patch.object(lib.asyncio, "sleep", _no_wait):
        await getattr(instance, method)(*args)

    callback.assert_called()


async def test_commands_do_not_interleave(instance: lib.BeurerInstance) -> None:
    """Two commands at once run one after the other, not packet by packet."""
    instance._light_on = True

    with patch.object(lib.asyncio, "sleep", _no_wait):
        await asyncio.gather(instance.set_white(100), instance.set_color((1, 2, 3)))

    # set_white finishes (brightness + status of both modes) before
    # set_color starts its mode switch.
    assert instance.sent[:3] == [
        [CMD_BRIGHTNESS, MODE_WHITE, 39],
        [CMD_STATUS, MODE_WHITE],
        [CMD_STATUS, MODE_RGB],
    ]
    assert instance.sent[3] == [CMD_MODE, MODE_RGB]


async def test_nested_command_does_not_deadlock(instance: lib.BeurerInstance) -> None:
    """turn_on calls set_effect/set_color under the same lock (re-entrant)."""
    instance._available = False  # first turn_on restores effect, color, brightness
    instance._mode = ColorMode.RGB

    with patch.object(lib.asyncio, "sleep", _no_wait):
        await asyncio.wait_for(instance.turn_on(), timeout=2)

    assert any(p[0] == CMD_EFFECT for p in instance.sent)


async def test_concurrent_connect_opens_one_connection() -> None:
    """A poll or command during a reconnect must not open a second client."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "TL100"
    inst = lib.BeurerInstance(device)
    client = MagicMock()
    client.is_connected = True

    async def slow_connect(*_args, **_kwargs):
        await _real_sleep(0.05)
        return client

    establish = AsyncMock(side_effect=slow_connect)
    with (
        patch.object(lib, "establish_connection", establish),
        patch.object(inst, "_setup_after_connect", AsyncMock(return_value=True)),
        patch.object(inst, "_start_watchdog"),
    ):
        results = await asyncio.gather(inst.connect(), inst.connect())

    assert results == [True, True]
    assert establish.await_count == 1


def test_stale_client_disconnect_is_ignored(instance: lib.BeurerInstance) -> None:
    """A replaced client's disconnect must not clear the live connection."""
    instance._light_on = True
    stale = MagicMock()

    instance._on_disconnect(stale)

    assert instance._write_uuid == "test-uuid"
    assert instance._light_on is True


def test_white_off_keeps_last_brightness(instance: lib.BeurerInstance) -> None:
    """White status "off" keeps brightness, so the next white is not 99 %."""
    instance._light_on = True
    instance._brightness = 77
    data = bytearray(13)
    data[8] = 1  # white status
    data[9] = 0  # off

    instance._handle_white_status(data)

    assert instance._light_on is False
    assert instance._brightness == 77


def test_push_update_sets_interval_before_scheduling() -> None:
    """The next refresh must be scheduled with the interval for the new state."""
    calls = []
    coordinator = MagicMock()
    coordinator.instance.mac = "AA:BB:CC:DD:EE:FF"
    coordinator._adjust_polling_interval.side_effect = lambda: calls.append("interval")
    coordinator.async_set_updated_data.side_effect = lambda _d: calls.append("data")

    BeurerDataUpdateCoordinator._handle_push_update(coordinator)

    assert calls == ["interval", "data"]


async def test_lost_packet_is_retried_after_link_error(
    instance: lib.BeurerInstance,
) -> None:
    """A packet lost to a dead link is sent once more after reconnecting."""
    del instance._send_packet  # use the real one, fake only _write
    calls = []

    async def write(_data: bytearray) -> bool:
        calls.append(1)
        instance._last_write_link_error = len(calls) == 1
        return len(calls) > 1

    with patch.object(instance, "_write", side_effect=write):
        assert await instance._send_packet([0x35, 1]) is True

    assert len(calls) == 2


async def test_watchdog_does_not_cancel_itself(instance: lib.BeurerInstance) -> None:
    """disconnect() called from the watchdog must not cancel the watchdog."""

    async def watchdog_body() -> int:
        instance._stop_watchdog()
        await _real_sleep(0)  # a cancel would raise here
        return 1

    task = asyncio.ensure_future(watchdog_body())
    instance._watchdog_task = task
    assert await task == 1


async def test_shutdown_stops_reconnects(instance: lib.BeurerInstance) -> None:
    """After unload, a disconnect callback must not schedule a reconnect."""
    with (
        patch.object(instance, "_safe_create_task") as create_task,
        patch.object(instance, "disconnect", AsyncMock()),
    ):
        await instance.shutdown()
        instance._on_disconnect(instance._client)
        await instance._auto_reconnect()

    create_task.assert_not_called()


def test_not_advertising_while_connected_stays_available(
    instance: lib.BeurerInstance,
) -> None:
    """Missing advertisements must not mark a connected lamp unavailable."""
    instance._available = True
    instance._ble_available = True

    instance.mark_unavailable()

    assert instance._available is True


async def test_filtered_confirmation_asks_status_again(
    instance: lib.BeurerInstance,
) -> None:
    """If the mode-switch filter dropped a status, ask once more afterwards."""

    async def run(drop: bool) -> int:
        instance.sent.clear()
        instance._color_on = False
        instance._light_on = True
        original = instance._send_packet

        async def record(packet: list[int]) -> bool:
            if drop and packet == [CMD_STATUS, MODE_WHITE]:
                instance._is_mode_switch_filtered(1)  # stale white during RGB switch
            return await original(packet)

        with (
            patch.object(instance, "_send_packet", record),
            patch.object(lib.asyncio, "sleep", _no_wait),
        ):
            await instance.set_color((1, 2, 3))
        return sum(1 for p in instance.sent if p[0] == CMD_STATUS)

    assert await run(drop=True) == await run(drop=False) + 2
    assert instance._filtered_during_switch is False


async def test_effect_off_without_color_does_not_switch_to_rgb(
    instance: lib.BeurerInstance,
) -> None:
    """effect Off while native white is on sends nothing (no RGB switch)."""
    instance._light_on = True
    instance._color_on = False

    with patch.object(lib.asyncio, "sleep", _no_wait):
        await instance.set_effect("Off")

    assert instance.sent == []
