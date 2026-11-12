"""Reconnect loop, watchdog and disconnect handling of BeurerInstance."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.exc import BleakError

from custom_components.beurer_daylight_lamps import beurer_daylight_lamps as mod
from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)

REAL_SLEEP = asyncio.sleep
SLEEP = "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.asyncio.sleep"


def make_instance(name: str = "TL100") -> BeurerInstance:
    """Return an instance without hass and without a client."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    return BeurerInstance(device, rssi=-60)


def connected_client() -> MagicMock:
    client = MagicMock()
    client.is_connected = True
    return client


class TestAutoReconnect:
    """_auto_reconnect retry loop."""

    async def test_skipped_when_loop_active_or_closing(self) -> None:
        inst = make_instance()
        inst.connect = AsyncMock()
        inst._reconnect_loop_active = True
        await inst._auto_reconnect()
        inst._reconnect_loop_active = False
        inst._closing = True
        await inst._auto_reconnect()
        inst.connect.assert_not_awaited()

    async def test_already_available(self) -> None:
        inst = make_instance()
        inst.connect = AsyncMock()
        inst._available = True
        inst._reconnect_backoff = 99
        await inst._auto_reconnect()
        assert inst._reconnect_backoff == mod.RECONNECT_INITIAL_BACKOFF
        assert not inst._reconnect_loop_active
        inst.connect.assert_not_awaited()

    async def test_not_reachable(self) -> None:
        inst = make_instance()
        inst.connect = AsyncMock()
        inst._ble_available = False
        await inst._auto_reconnect()
        inst.connect.assert_not_awaited()

    async def test_retries_with_backoff_until_success(self) -> None:
        inst = make_instance()
        inst._available = False
        inst.connect = AsyncMock(side_effect=[False, BleakError("x"), True])
        with patch(SLEEP, new=AsyncMock()) as sleep:
            await inst._auto_reconnect()
        assert inst.connect.await_count == 3
        delays = [c.args[0] for c in sleep.await_args_list]
        assert delays[0] == mod.RECONNECT_INITIAL_BACKOFF
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]
        assert inst._reconnect_backoff == mod.RECONNECT_INITIAL_BACKOFF

    async def test_backoff_is_capped(self) -> None:
        inst = make_instance()
        inst._reconnect_backoff = mod.RECONNECT_MAX_BACKOFF
        inst.connect = AsyncMock(side_effect=[OSError("x"), True])
        with patch(SLEEP, new=AsyncMock()):
            await inst._auto_reconnect()
        assert inst.connect.await_count == 2

    @pytest.mark.parametrize("change", ["available", "unreachable", "closing"])
    async def test_state_changes_during_backoff(self, change: str) -> None:
        inst = make_instance()
        inst.connect = AsyncMock()

        async def fake_sleep(_delay: float) -> None:
            if change == "available":
                inst._available = True
            elif change == "unreachable":
                inst._ble_available = False
            else:
                inst._closing = True

        with patch(SLEEP, new=fake_sleep):
            await inst._auto_reconnect()
        inst.connect.assert_not_awaited()

    async def test_cancelled(self) -> None:
        inst = make_instance()
        inst.connect = AsyncMock(side_effect=asyncio.CancelledError)
        with patch(SLEEP, new=AsyncMock()), pytest.raises(asyncio.CancelledError):
            await inst._auto_reconnect()
        assert not inst._reconnect_loop_active


class TestWatchdog:
    """Connection watchdog."""

    async def _run(self, inst: BeurerInstance, sleep) -> None:
        with patch(SLEEP, new=sleep):
            inst._start_watchdog()
            task = inst._watchdog_task
            assert task is not None
            await task
        assert inst._watchdog_task is None

    async def test_stops_when_disconnected(self) -> None:
        inst = make_instance()
        await self._run(inst, AsyncMock())

    async def test_stale_connection_forces_reconnect(self) -> None:
        inst = make_instance()
        inst._client = connected_client()
        inst._light_on = True
        inst._available = True
        inst._last_seen = 0
        inst.disconnect = AsyncMock()
        inst._auto_reconnect = AsyncMock()
        await self._run(inst, AsyncMock())
        await asyncio.sleep(0)
        inst.disconnect.assert_awaited_once()
        inst._auto_reconnect.assert_awaited_once()

    async def test_healthy_then_disconnected(self) -> None:
        inst = make_instance()
        inst._client = connected_client()
        calls = 0

        async def sleep(_d: float) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                inst._client.is_connected = False

        await self._run(inst, sleep)
        assert calls == 2

    async def test_error_ends_loop(self) -> None:
        inst = make_instance()
        await self._run(inst, AsyncMock(side_effect=BleakError("x")))

    async def test_restart_cancels_old_task(self) -> None:
        inst = make_instance()
        inst._client = connected_client()
        never = asyncio.Event()

        async def sleep(_d: float) -> None:
            await never.wait()

        with patch(SLEEP, new=sleep):
            inst._start_watchdog()
            first = inst._watchdog_task
            await REAL_SLEEP(0)
            inst._start_watchdog()
            second = inst._watchdog_task
            with pytest.raises(asyncio.CancelledError):
                await first
            inst._stop_watchdog()
            with pytest.raises(asyncio.CancelledError):
                await second


class TestOnDisconnect:
    """Disconnect callback."""

    def test_stale_client_ignored(self) -> None:
        inst = make_instance()
        inst._client = connected_client()
        inst._available = True
        inst._on_disconnect(MagicMock())
        assert inst._available

    def test_closing_ignored(self) -> None:
        inst = make_instance()
        inst._available = True
        inst._closing = True
        inst._on_disconnect(MagicMock())
        assert inst._available

    async def test_schedules_update_and_reconnect(self) -> None:
        inst = make_instance()
        client = connected_client()
        inst._client = client
        inst._available = True
        inst._write_uuid = "w"
        inst._connection_start_time = 1.0
        inst.set_update_callback(MagicMock())
        with patch.object(inst, "_safe_create_task") as create:
            inst._on_disconnect(client)
        assert not inst._available
        assert inst._write_uuid is None
        assert inst._connection_start_time is None
        names = [c.args[1] for c in create.call_args_list]
        assert names == ["beurer_disconnect_update", "beurer_disconnect_reconnect"]
        for c in create.call_args_list:
            c.args[0].close()


class TestSafeCreateTask:
    """Fire-and-forget tasks."""

    async def test_errors_are_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        inst = make_instance()

        async def boom() -> None:
            raise BleakError("broken")

        task = inst._safe_create_task(boom(), "t")
        await task
        assert "broken" in caplog.text

    async def test_cancel_propagates(self) -> None:
        inst = make_instance()
        task = inst._safe_create_task(asyncio.Event().wait(), "t")
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    def test_no_loop(self) -> None:
        inst = make_instance()

        async def noop() -> None:
            return None

        coro = noop()
        with patch(
            "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.asyncio.create_task",
            side_effect=RuntimeError,
        ):
            assert inst._safe_create_task(coro) is None
        coro.close()

    def test_uses_hass(self) -> None:
        inst = make_instance()
        inst._hass = MagicMock()
        coro = inst._safe_create_task(asyncio.sleep(0), "named")
        assert coro is inst._hass.async_create_background_task.return_value
        inst._hass.async_create_background_task.call_args.args[0].close()


class TestMarkSeen:
    """Advertisement handling."""

    def test_reachable_again_triggers_reconnect(self) -> None:
        inst = make_instance()
        inst._ble_available = False
        with patch.object(inst, "_safe_create_task") as create:
            inst.mark_seen()
        names = [c.args[1] for c in create.call_args_list]
        assert names == ["beurer_ble_reachable_update", "beurer_auto_reconnect"]
        for c in create.call_args_list:
            c.args[0].close()

    def test_cooldown(self) -> None:
        inst = make_instance()
        inst._last_reconnect_attempt = mod.time.time()
        with patch.object(inst, "_safe_create_task") as create:
            inst.mark_seen()
        create.assert_not_called()

    def test_connected_lamp_stays_available(self) -> None:
        inst = make_instance()
        inst._client = connected_client()
        inst.mark_unavailable()
        assert inst._ble_available
