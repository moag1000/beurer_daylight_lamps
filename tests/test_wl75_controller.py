"""Tests for the WL75 controller (protocol family 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.beurer_daylight_lamps.const import (
    CMD_WL75_ALARM_WRITE,
    CMD_WL75_RADIO_CHANNEL,
    CMD_WL75_RADIO_FINE_TUNE,
    CMD_WL75_RADIO_POWER,
    CMD_WL75_RADIO_PRESETS_1,
    CMD_WL75_RADIO_PRESETS_2,
    CMD_WL75_RADIO_SAVE_FREQ,
    CMD_WL75_RADIO_SEEK,
    CMD_WL75_RADIO_STATUS,
    CMD_WL75_RADIO_TIMER_TOGGLE,
    CMD_WL75_RADIO_TIMER_VALUE,
    CMD_WL75_RADIO_VOLUME,
    RESP_WL75_ALARM,
    RESP_WL75_RADIO_CHANNEL,
    RESP_WL75_RADIO_FINE_TUNE,
    RESP_WL75_RADIO_POWER,
    RESP_WL75_RADIO_PRESETS_1,
    RESP_WL75_RADIO_PRESETS_2,
    RESP_WL75_RADIO_SEARCH,
    RESP_WL75_RADIO_SLEEP_TIMER_ENABLE,
    RESP_WL75_RADIO_SLEEP_TIMER_VALUE,
    RESP_WL75_RADIO_STATUS,
    RESP_WL75_RADIO_VOLUME,
    RESP_WL75_SAVE_RADIO_FREQ,
    RESP_WL75_UPDATE_ALARM,
)
from custom_components.beurer_daylight_lamps.wl75 import WL75Controller
from custom_components.beurer_daylight_lamps.wl90 import AlarmItem


@pytest.fixture
def instance() -> MagicMock:
    """Return a fake BeurerInstance."""
    inst = MagicMock()
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst._send_packet = AsyncMock(return_value=True)
    return inst


@pytest.fixture
def ctrl(instance: MagicMock) -> WL75Controller:
    """Return a WL75 controller."""
    return WL75Controller(instance)


@pytest.fixture(autouse=True)
def no_sleep():
    """Skip command delays."""
    with patch(
        "custom_components.beurer_daylight_lamps.wl75.asyncio.sleep",
        new=AsyncMock(),
    ):
        yield


def test_two_alarm_slots(ctrl: WL75Controller) -> None:
    assert [a.slot for a in ctrl.alarms] == [0, 1]


class TestRadio:
    """Radio commands."""

    async def test_on_off(self, ctrl: WL75Controller, instance: MagicMock) -> None:
        assert await ctrl.radio_on()
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_POWER, 1])
        assert ctrl.radio.is_on
        assert await ctrl.radio_off()
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_POWER, 0])
        assert not ctrl.radio.is_on

    async def test_failures_keep_state(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.return_value = False
        assert not await ctrl.radio_on()
        assert not ctrl.radio.is_on
        ctrl.radio.is_on = True
        assert not await ctrl.radio_off()
        assert ctrl.radio.is_on
        assert not await ctrl.set_radio_volume(1)
        assert ctrl.radio.volume == 5
        assert not await ctrl.select_radio_preset(3)
        assert ctrl.radio.channel == 0
        assert not await ctrl.set_radio_sleep_timer(0)
        assert not await ctrl.set_radio_sleep_timer(20)
        assert not await ctrl.sync_alarm(0, AlarmItem(enabled=True))
        assert not ctrl.alarms[0].enabled

    async def test_volume(self, ctrl: WL75Controller, instance: MagicMock) -> None:
        await ctrl.set_radio_volume(99)
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_VOLUME, 10])
        assert ctrl.radio.volume == 10

    async def test_preset_uses_known_frequency(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        ctrl.radio.presets = [875, 1000, 1040]
        await ctrl.select_radio_preset(3)
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_CHANNEL, 3])
        assert ctrl.radio.channel == 2
        assert ctrl.radio.frequency == 1040
        await ctrl.select_radio_preset(11)
        assert ctrl.radio.channel == 9
        assert ctrl.radio.frequency == 1040

    async def test_seek_and_tune(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        await ctrl.radio_seek()
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_SEEK, 0])
        await ctrl.radio_seek(direction=0, auto_seek=False)
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_FINE_TUNE, 1])

    async def test_sleep_timer(self, ctrl: WL75Controller, instance: MagicMock) -> None:
        assert await ctrl.set_radio_sleep_timer(20)
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_TIMER_VALUE, 20])
        assert ctrl.radio.sleep_timer_on
        assert ctrl.radio.sleep_timer_minutes == 20
        assert await ctrl.set_radio_sleep_timer(0)
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_TIMER_TOGGLE, 0])
        assert not ctrl.radio.sleep_timer_on
        assert ctrl.radio.sleep_timer_minutes == 0

    async def test_sleep_timer_value_fails(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.side_effect = [True, False]
        assert not await ctrl.set_radio_sleep_timer(5)
        assert not ctrl.radio.sleep_timer_on

    async def test_save_and_query(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        await ctrl.save_radio_frequency()
        instance._send_packet.assert_awaited_with([CMD_WL75_RADIO_SAVE_FREQ])
        instance._send_packet.reset_mock()
        assert await ctrl.query_radio_status()
        assert [c.args[0] for c in instance._send_packet.await_args_list] == [
            [CMD_WL75_RADIO_STATUS],
            [CMD_WL75_RADIO_PRESETS_1],
            [CMD_WL75_RADIO_PRESETS_2],
        ]


async def test_music_not_supported(ctrl: WL75Controller, instance: MagicMock) -> None:
    assert not await ctrl.music_on()
    assert not await ctrl.music_off()
    assert not await ctrl.set_music_volume(3)
    assert not await ctrl.set_music_sleep_timer(3)
    assert not await ctrl.query_music_status()
    instance._send_packet.assert_not_awaited()


class TestAlarmSync:
    """Alarm writes."""

    async def test_invalid_slot(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        assert not await ctrl.sync_alarm(2)
        instance._send_packet.assert_not_awaited()

    async def test_stored_alarm(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        assert await ctrl.sync_alarm(1)
        instance._send_packet.assert_awaited_with(
            [CMD_WL75_ALARM_WRITE, 2, 0, 7, 0x3E, 0, 5, 4, 0, 20, 50]
        )

    async def test_enabled_alarm(
        self, ctrl: WL75Controller, instance: MagicMock
    ) -> None:
        alarm = AlarmItem(enabled=True, hour=6, minute=15, days=0x41, snooze_minutes=1)
        assert await ctrl.sync_alarm(0, alarm)
        instance._send_packet.assert_awaited_with(
            [CMD_WL75_ALARM_WRITE, 1, 15, 6, 0xC1, 0, 5, 1, 0, 20, 50]
        )
        assert ctrl.alarms[0] is alarm


class TestNotifications:
    """Payload parsing."""

    def test_unknown(self, ctrl: WL75Controller) -> None:
        assert not ctrl.handle_notification(0xEE, bytearray([0xEE]))

    def test_radio_status(self, ctrl: WL75Controller) -> None:
        payload = bytearray([RESP_WL75_RADIO_STATUS, 1, 4, 0x04, 0x10, 12, 1, 0])
        assert ctrl.handle_notification(RESP_WL75_RADIO_STATUS, payload)
        assert ctrl.radio.is_on
        assert ctrl.radio.channel == 3
        assert ctrl.radio.frequency == 0x0410
        assert ctrl.radio.volume == 10
        assert ctrl.radio.sleep_timer_minutes == 1

    def test_radio_status_timer_off_and_short(self, ctrl: WL75Controller) -> None:
        payload = bytearray([RESP_WL75_RADIO_STATUS, 0, 0, 0, 0, 3, 0, 9])
        ctrl.handle_notification(RESP_WL75_RADIO_STATUS, payload)
        assert ctrl.radio.channel == 0
        assert ctrl.radio.sleep_timer_minutes == 0
        assert ctrl.handle_notification(
            RESP_WL75_RADIO_STATUS, bytearray([RESP_WL75_RADIO_STATUS, 1])
        )
        assert not ctrl.radio.is_on

    def test_presets(self, ctrl: WL75Controller) -> None:
        part1 = bytearray([RESP_WL75_RADIO_PRESETS_1])
        for freq in (875, 900, 950, 1000, 1040):
            part1 += bytes([freq >> 8, freq & 0xFF])
        assert ctrl.handle_notification(RESP_WL75_RADIO_PRESETS_1, part1)
        assert ctrl.radio.presets[:5] == [875, 900, 950, 1000, 1040]
        # Part 2 is short: only the first two presets are present
        part2 = bytearray([RESP_WL75_RADIO_PRESETS_2, 0x04, 0x1A, 0x04, 0x24])
        assert ctrl.handle_notification(RESP_WL75_RADIO_PRESETS_2, part2)
        assert ctrl.radio.presets[5:] == [0x041A, 0x0424, 0, 0, 0]
        assert ctrl.radio.presets[:5] == [875, 900, 950, 1000, 1040]

    @pytest.mark.parametrize(
        "resp", [RESP_WL75_RADIO_SEARCH, RESP_WL75_RADIO_FINE_TUNE]
    )
    def test_tuned_frequency(self, ctrl: WL75Controller, resp: int) -> None:
        assert ctrl.handle_notification(resp, bytearray([resp, 0, 0x03, 0xE8]))
        assert ctrl.radio.frequency == 1000
        assert ctrl.handle_notification(resp, bytearray([resp, 0]))
        assert ctrl.radio.frequency == 1000

    def test_alarm(self, ctrl: WL75Controller) -> None:
        payload = bytearray([RESP_WL75_ALARM, 0x82, 30, 6, 0xBE, 3, 8, 4, 0, 10, 70])
        assert ctrl.handle_notification(RESP_WL75_ALARM, payload)
        alarm = ctrl.alarms[1]
        assert alarm.enabled
        assert (alarm.hour, alarm.minute) == (6, 30)
        assert alarm.days == 0x3E
        assert alarm.tone == 3
        assert alarm.volume == 8
        assert alarm.snooze_minutes == 10
        assert alarm.sunrise_enabled
        assert alarm.sunrise_brightness == 70

    def test_alarm_sunrise_disabled(self, ctrl: WL75Controller) -> None:
        payload = bytearray([RESP_WL75_ALARM, 1, 0, 7, 0x00, 0, 5, 0, 0, 0, 0])
        ctrl.handle_notification(RESP_WL75_ALARM, payload)
        alarm = ctrl.alarms[0]
        assert not alarm.enabled
        assert not alarm.sunrise_enabled
        assert alarm.snooze_minutes == 1

    def test_alarm_invalid(self, ctrl: WL75Controller) -> None:
        bad_slot = bytearray([RESP_WL75_ALARM, 5, 30, 6, 0xBE, 3, 8, 4, 0, 10, 70])
        assert ctrl.handle_notification(RESP_WL75_ALARM, bad_slot)
        assert ctrl.handle_notification(RESP_WL75_ALARM, bytearray([RESP_WL75_ALARM]))
        assert not any(a.enabled for a in ctrl.alarms)

    @pytest.mark.parametrize(
        "resp",
        [
            RESP_WL75_RADIO_POWER,
            RESP_WL75_RADIO_CHANNEL,
            RESP_WL75_RADIO_VOLUME,
            RESP_WL75_RADIO_SLEEP_TIMER_ENABLE,
            RESP_WL75_RADIO_SLEEP_TIMER_VALUE,
            RESP_WL75_SAVE_RADIO_FREQ,
            RESP_WL75_UPDATE_ALARM,
        ],
    )
    def test_acks(self, ctrl: WL75Controller, resp: int) -> None:
        assert ctrl.handle_notification(resp, bytearray([resp]))
