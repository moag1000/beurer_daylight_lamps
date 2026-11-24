"""Therapy minutes follow the lamp state on every path (issue #17).

The tests feed real BLE notifications into ``_handle_notification`` and use
the real commands where possible, so tracking is checked the way it runs on a
lamp: native white, RGB white, WL75 channels, timer end, off and disconnect.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    RESP_LIGHT_TIMER_END,
    RESP_STATUS,
    RESP_WL75_LIGHT_STATUS,
    RESP_WL75_MOODLIGHT_STATUS,
    RESP_WL75_TIMER_END,
)


def _tl_status(version: int, on: bool = True, brightness_pct: int = 100) -> bytearray:
    """Build a TL status notification (1 = white, 2 = RGB, 255 = off)."""
    data = bytearray(17)
    data[6] = 0x0B  # payload length: a status, not a heartbeat
    data[7] = RESP_STATUS
    data[8] = version
    data[9] = 1 if on else 0
    data[10] = brightness_pct
    return data


def _tl_rgb(
    rgb: tuple[int, int, int], brightness_pct: int = 100, effect: int = 0
) -> bytearray:
    data = _tl_status(2, on=True, brightness_pct=brightness_pct)
    data[13:16] = bytes(rgb)
    data[16] = effect
    return data


def _tl_timer_end() -> bytearray:
    data = bytearray(10)
    data[7] = RESP_LIGHT_TIMER_END
    data[8] = 1  # 1 = lamp turned off
    return data


def _wl75_frame(payload: list[int]) -> bytearray:
    plen = len(payload) + 1
    checksum = plen
    for byte in payload:
        checksum ^= byte
    return bytearray([0xFE, 0xEF, plen, *payload, checksum])


def _make(name: str) -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    instance = BeurerInstance(device)
    instance._available = True
    return instance


@pytest.fixture
def tl() -> BeurerInstance:
    return _make("TL100")


@pytest.fixture
def wl75() -> BeurerInstance:
    return _make("WL75_1234")


async def _notify(instance: BeurerInstance, data: bytearray) -> None:
    await instance._handle_notification(MagicMock(), data)


def _run_for(instance: BeurerInstance, minutes: float) -> None:
    """Let the running session have lasted ``minutes`` already."""
    session = instance.therapy_tracker._current_session
    assert session is not None, "no therapy session is running"
    session.start_time -= timedelta(minutes=minutes)


class TestNativeWhite:
    """TL100 daylight on the native white LEDs."""

    async def test_white_counts_and_survives_rgb_off_status(
        self, tl: BeurerInstance
    ) -> None:
        await _notify(tl, _tl_status(1, brightness_pct=99))
        await _notify(tl, _tl_status(2, on=False))  # RGB channel reports off
        assert tl.therapy_tracker.has_active_session
        _run_for(tl, 30)
        assert tl.therapy_today_minutes == pytest.approx(30, abs=0.1)

    async def test_off_keeps_minutes(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_status(1))
        _run_for(tl, 12)
        await _notify(tl, _tl_status(255))
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(12, abs=0.1)

    async def test_dimming_below_therapy_level_keeps_minutes(
        self, tl: BeurerInstance
    ) -> None:
        await _notify(tl, _tl_status(1))
        _run_for(tl, 10)
        await _notify(tl, _tl_status(1, brightness_pct=50))
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(10, abs=0.1)
        # Back to full daylight starts a new session
        await _notify(tl, _tl_status(1))
        assert tl.therapy_tracker.has_active_session

    async def test_timer_end_ends_session(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_status(1))
        _run_for(tl, 5)
        tl.emit_lamp_event = MagicMock()
        await _notify(tl, _tl_timer_end())
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(5, abs=0.1)

    async def test_set_white_full_starts_session(self, tl: BeurerInstance) -> None:
        """The "Start light therapy" button (set_white(255)) is tracked."""
        tl._send_packet = AsyncMock(return_value=True)
        tl._request_status = AsyncMock()
        tl._switch_to_mode = AsyncMock()
        await tl.set_white(255)
        assert tl.therapy_tracker.has_active_session

    async def test_turn_off_ends_session(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_status(1))
        _run_for(tl, 3)
        tl._send_packet = AsyncMock(return_value=True)
        tl._request_status = AsyncMock()
        await tl.turn_off()
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(3, abs=0.1)


class TestRgbWhite:
    """Bright, balanced white from the RGB channel."""

    async def test_rgb_white_counts(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_rgb((255, 255, 255)))
        assert tl.therapy_tracker.has_active_session

    async def test_effect_does_not_count(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_rgb((255, 255, 255), effect=2))  # Rainbow
        assert not tl.therapy_tracker.has_active_session

    async def test_color_change_keeps_minutes(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_rgb((255, 255, 255)))
        _run_for(tl, 8)
        await _notify(tl, _tl_rgb((255, 120, 50)))
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(8, abs=0.1)


class TestWL75:
    """WL75 (protocol 2) white light and mood light."""

    async def test_white_light_counts(self, wl75: BeurerInstance) -> None:
        await _notify(wl75, _wl75_frame([RESP_WL75_LIGHT_STATUS, 1, 100, 0, 0]))
        assert wl75.therapy_tracker.has_active_session
        _run_for(wl75, 20)
        await _notify(wl75, _wl75_frame([RESP_WL75_LIGHT_STATUS, 0, 100, 0, 0]))
        assert not wl75.therapy_tracker.has_active_session
        assert wl75.therapy_today_minutes == pytest.approx(20, abs=0.1)

    async def test_mood_light_keeps_white_brightness(
        self, wl75: BeurerInstance
    ) -> None:
        """Mood light status no longer overwrites the white brightness."""
        await _notify(wl75, _wl75_frame([RESP_WL75_LIGHT_STATUS, 1, 100, 0, 0]))
        await _notify(
            wl75,
            _wl75_frame([RESP_WL75_MOODLIGHT_STATUS, 1, 30, 0, 0, 255, 0, 0, 0]),
        )
        assert wl75.white_brightness == 255
        assert wl75.color_brightness == int(30 / 100 * 255)

    async def test_timer_end_ends_session(self, wl75: BeurerInstance) -> None:
        await _notify(wl75, _wl75_frame([RESP_WL75_LIGHT_STATUS, 1, 100, 1, 30]))
        _run_for(wl75, 30)
        wl75.emit_lamp_event = MagicMock()
        await _notify(wl75, _wl75_frame([RESP_WL75_TIMER_END, 2]))
        assert not wl75.therapy_tracker.has_active_session
        assert wl75.therapy_today_minutes == pytest.approx(30, abs=0.1)


class TestConnectionLoss:
    """Minutes are not counted while the lamp state is unknown."""

    async def test_unexpected_disconnect_ends_session(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_status(1))
        _run_for(tl, 4)
        tl._ble_available = False  # no reconnect attempt in this test
        tl._on_disconnect(tl._client)
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(4, abs=0.1)

    async def test_disconnect_ends_session(self, tl: BeurerInstance) -> None:
        await _notify(tl, _tl_status(1))
        _run_for(tl, 6)
        await tl.disconnect()
        assert not tl.therapy_tracker.has_active_session
        assert tl.therapy_today_minutes == pytest.approx(6, abs=0.1)
