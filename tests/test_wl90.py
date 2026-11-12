"""Tests for the WL90 controller (radio, BT speaker, alarms)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.beurer_daylight_lamps.const import (
    CMD_ALARM_SYNC,
    CMD_MUSIC_CLOSE,
    CMD_MUSIC_QUERY,
    CMD_MUSIC_TIMER_TOGGLE,
    CMD_MUSIC_TIMER_VALUE,
    CMD_MUSIC_TOGGLE,
    CMD_MUSIC_VOLUME,
    CMD_RADIO_POWER,
    CMD_RADIO_PRESET,
    CMD_RADIO_SAVE_FREQ,
    CMD_RADIO_SYNC_STATUS,
    CMD_RADIO_TIMER_TOGGLE,
    CMD_RADIO_TIMER_VALUE,
    CMD_RADIO_TUNE,
    CMD_RADIO_VOLUME,
    EVENT_TYPE_SLEEP_TIMER_FINISHED,
    RESP_ALARM,
    RESP_MUSIC_INFO,
    RESP_MUSIC_STATUS,
    RESP_MUSIC_TIMER,
    RESP_MUSIC_TIMER_END,
    RESP_MUSIC_TOGGLE,
    RESP_RADIO_INFO,
    RESP_RADIO_POWER,
    RESP_RADIO_PRESET,
    RESP_RADIO_SAVE,
    RESP_RADIO_STATUS,
    RESP_RADIO_TIMER_END,
    RESP_RADIO_TUNE,
)
from custom_components.beurer_daylight_lamps.wl90 import (
    AlarmItem,
    RadioState,
    WL90Controller,
)


@pytest.fixture
def instance() -> MagicMock:
    """Return a fake BeurerInstance."""
    inst = MagicMock()
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst._send_packet = AsyncMock(return_value=True)
    inst.emit_lamp_event = MagicMock()
    return inst


@pytest.fixture
def ctrl(instance: MagicMock) -> WL90Controller:
    """Return a WL90 controller."""
    return WL90Controller(instance)


@pytest.fixture(autouse=True)
def no_sleep():
    """Skip command delays."""
    with patch(
        "custom_components.beurer_daylight_lamps.wl90.asyncio.sleep",
        new=AsyncMock(),
    ):
        yield


def _packet(resp: int, *payload: int) -> bytearray:
    """Build a notification with resp at index 7 followed by payload."""
    return bytearray([0] * 7 + [resp, *payload])


class TestAlarmItem:
    """AlarmItem helpers."""

    @pytest.mark.parametrize(
        ("minutes", "index"), [(1, 0), (3, 2), (10, 3), (25, 5), (30, 5), (99, 5)]
    )
    def test_snooze_to_index(self, minutes: int, index: int) -> None:
        assert AlarmItem(snooze_minutes=minutes)._snooze_to_index() == index

    def test_snooze_from_index(self) -> None:
        assert AlarmItem._snooze_from_index(0) == 1
        assert AlarmItem._snooze_from_index(5) == 30
        assert AlarmItem._snooze_from_index(9) == 10
        assert AlarmItem._snooze_from_index(-1) == 10

    def test_days_list_roundtrip(self) -> None:
        alarm = AlarmItem()
        assert alarm.days_list == ["Mon", "Tue", "Wed", "Thu", "Fri"]
        alarm.days_list = ["Sun", "Sat", "Bogus"]
        assert alarm.days == 0b1000001
        assert alarm.days_list == ["Sun", "Sat"]

    def test_radio_frequency_mhz(self) -> None:
        assert RadioState().frequency_mhz == 0.0
        assert RadioState(frequency=1040).frequency_mhz == 104.0


class TestRadio:
    """Radio commands."""

    async def test_on_off(self, ctrl: WL90Controller, instance: MagicMock) -> None:
        assert await ctrl.radio_on()
        assert ctrl.radio.is_on
        instance._send_packet.assert_awaited_with([CMD_RADIO_POWER, 1])
        assert await ctrl.radio_off()
        assert not ctrl.radio.is_on
        instance._send_packet.assert_awaited_with([CMD_RADIO_POWER, 0])

    async def test_failed_send_keeps_state(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.return_value = False
        assert not await ctrl.radio_on()
        assert not ctrl.radio.is_on
        ctrl.radio.is_on = True
        assert not await ctrl.radio_off()
        assert ctrl.radio.is_on
        assert not await ctrl.set_radio_volume(3)
        assert ctrl.radio.volume == 5
        assert not await ctrl.select_radio_preset(2)
        assert ctrl.radio.channel == 0
        assert not await ctrl.set_radio_sleep_timer(0)
        assert not await ctrl.set_radio_sleep_timer(30)
        assert not ctrl.radio.sleep_timer_minutes

    async def test_volume_clamped(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        await ctrl.set_radio_volume(42)
        instance._send_packet.assert_awaited_with([CMD_RADIO_VOLUME, 10])
        assert ctrl.radio.volume == 10
        await ctrl.set_radio_volume(-3)
        assert ctrl.radio.volume == 0

    async def test_preset_clamped(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        await ctrl.select_radio_preset(0)
        instance._send_packet.assert_awaited_with([CMD_RADIO_PRESET, 1])
        await ctrl.select_radio_preset(12)
        assert ctrl.radio.channel == 10

    async def test_seek(self, ctrl: WL90Controller, instance: MagicMock) -> None:
        await ctrl.radio_seek()
        instance._send_packet.assert_awaited_with([CMD_RADIO_TUNE, 1, 1])
        await ctrl.radio_seek(direction=0, auto_seek=False)
        instance._send_packet.assert_awaited_with([CMD_RADIO_TUNE, 0, 0])

    async def test_sleep_timer(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        assert await ctrl.set_radio_sleep_timer(30)
        assert instance._send_packet.await_args_list[-2].args[0] == [
            CMD_RADIO_TIMER_TOGGLE,
            1,
        ]
        instance._send_packet.assert_awaited_with([CMD_RADIO_TIMER_VALUE, 30])
        assert ctrl.radio.sleep_timer_on
        assert ctrl.radio.sleep_timer_minutes == 30
        assert await ctrl.set_radio_sleep_timer(0)
        instance._send_packet.assert_awaited_with([CMD_RADIO_TIMER_TOGGLE, 0])
        assert not ctrl.radio.sleep_timer_on

    async def test_sleep_timer_value_fails(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.side_effect = [True, False]
        assert not await ctrl.set_radio_sleep_timer(15)
        assert not ctrl.radio.sleep_timer_on

    async def test_save_and_query(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        await ctrl.save_radio_frequency(3)
        instance._send_packet.assert_awaited_with([CMD_RADIO_SAVE_FREQ, 3])
        await ctrl.query_radio_status()
        instance._send_packet.assert_awaited_with([CMD_RADIO_SYNC_STATUS])


class TestMusic:
    """Bluetooth speaker commands."""

    async def test_on_off(self, ctrl: WL90Controller, instance: MagicMock) -> None:
        assert await ctrl.music_on()
        instance._send_packet.assert_awaited_with([CMD_MUSIC_TOGGLE, 1])
        assert ctrl.music.is_on
        assert await ctrl.music_off()
        instance._send_packet.assert_awaited_with([CMD_MUSIC_CLOSE])
        assert not ctrl.music.is_on

    async def test_failed_send_keeps_state(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.return_value = False
        assert not await ctrl.music_on()
        assert not ctrl.music.is_on
        ctrl.music.is_on = True
        assert not await ctrl.music_off()
        assert ctrl.music.is_on
        assert not await ctrl.set_music_volume(2)
        assert ctrl.music.volume == 5
        assert not await ctrl.set_music_sleep_timer(0)
        assert not await ctrl.set_music_sleep_timer(10)

    async def test_volume(self, ctrl: WL90Controller, instance: MagicMock) -> None:
        await ctrl.set_music_volume(11)
        instance._send_packet.assert_awaited_with([CMD_MUSIC_VOLUME, 10])
        assert ctrl.music.volume == 10

    async def test_sleep_timer(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        assert await ctrl.set_music_sleep_timer(45)
        instance._send_packet.assert_awaited_with([CMD_MUSIC_TIMER_VALUE, 45])
        assert ctrl.music.sleep_timer_on
        assert ctrl.music.sleep_timer_minutes == 45
        assert await ctrl.set_music_sleep_timer(0)
        instance._send_packet.assert_awaited_with([CMD_MUSIC_TIMER_TOGGLE, 0])
        assert not ctrl.music.sleep_timer_on

    async def test_sleep_timer_value_fails(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.side_effect = [True, False]
        assert not await ctrl.set_music_sleep_timer(15)
        assert not ctrl.music.sleep_timer_on

    async def test_query(self, ctrl: WL90Controller, instance: MagicMock) -> None:
        await ctrl.query_music_status()
        instance._send_packet.assert_awaited_with([CMD_MUSIC_QUERY])


class TestAlarmSync:
    """Alarm sync."""

    async def test_invalid_slot(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        assert not await ctrl.sync_alarm(5)
        instance._send_packet.assert_not_awaited()

    async def test_stored_alarm(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        assert await ctrl.sync_alarm(0)
        packet = instance._send_packet.await_args.args[0]
        assert packet[0] == CMD_ALARM_SYNC
        assert packet[2:] == [0, 0, 7, 0x3E, 0, 5, 3, 1, 20, 50]

    async def test_new_alarm_stored(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        alarm = AlarmItem(
            slot=2, enabled=True, hour=6, minute=30, sunrise_enabled=False
        )
        assert await ctrl.sync_alarm(2, alarm)
        assert ctrl.alarms[2] is alarm
        packet = instance._send_packet.await_args.args[0]
        assert packet[2:5] == [1, 30, 6]
        assert packet[9] == 0

    async def test_failed_sync_not_stored(
        self, ctrl: WL90Controller, instance: MagicMock
    ) -> None:
        instance._send_packet.return_value = False
        alarm = AlarmItem(slot=1, enabled=True)
        assert not await ctrl.sync_alarm(1, alarm)
        assert ctrl.alarms[1] is not alarm


class TestNotifications:
    """Notification parsing."""

    def test_unknown_response(self, ctrl: WL90Controller) -> None:
        assert not ctrl.handle_notification(0x01, _packet(0x01))

    def test_radio_status(self, ctrl: WL90Controller) -> None:
        data = _packet(RESP_RADIO_STATUS, 1, 3, 0x04, 0x10, 15, 1, 0)
        assert ctrl.handle_notification(RESP_RADIO_STATUS, data)
        assert ctrl.radio.is_on
        assert ctrl.radio.channel == 3
        assert ctrl.radio.frequency == 0x0410
        assert ctrl.radio.volume == 10
        assert ctrl.radio.sleep_timer_on
        assert ctrl.radio.sleep_timer_minutes == 1

    def test_radio_status_timer_off(self, ctrl: WL90Controller) -> None:
        data = _packet(RESP_RADIO_STATUS, 0, 0, 0, 0, 4, 0, 30)
        ctrl.handle_notification(RESP_RADIO_STATUS, data)
        assert not ctrl.radio.sleep_timer_on
        assert ctrl.radio.sleep_timer_minutes == 0

    def test_radio_status_short(self, ctrl: WL90Controller) -> None:
        assert ctrl.handle_notification(RESP_RADIO_STATUS, _packet(RESP_RADIO_STATUS))
        assert not ctrl.radio.is_on

    def test_radio_info(self, ctrl: WL90Controller) -> None:
        assert ctrl.handle_notification(RESP_RADIO_INFO, _packet(RESP_RADIO_INFO, 1, 2))
        assert ctrl.handle_notification(RESP_RADIO_INFO, _packet(RESP_RADIO_INFO))

    @pytest.mark.parametrize(("index", "slot"), [(1, 0), (0x87, 1), (3, 2)])
    def test_alarm_response(self, ctrl: WL90Controller, index: int, slot: int) -> None:
        data = _packet(RESP_ALARM, index, 1, 6, 45, 0x41, 2, 7, 4, 1, 15, 80)
        assert ctrl.handle_notification(RESP_ALARM, data)
        alarm = ctrl.alarms[slot]
        assert alarm.enabled
        assert (alarm.hour, alarm.minute) == (6, 45)
        assert alarm.days_list == ["Sun", "Sat"]
        assert alarm.tone == 2
        assert alarm.volume == 7
        assert alarm.snooze_minutes == 20
        assert alarm.sunrise_enabled
        assert alarm.sunrise_time == 15
        assert alarm.sunrise_brightness == 80

    def test_alarm_unknown_index_and_short(self, ctrl: WL90Controller) -> None:
        data = _packet(RESP_ALARM, 9, 1, 6, 45, 0x41, 2, 7, 4, 1, 15, 80)
        assert ctrl.handle_notification(RESP_ALARM, data)
        assert not any(a.enabled for a in ctrl.alarms)
        assert ctrl.handle_notification(RESP_ALARM, _packet(RESP_ALARM, 1))

    def test_music_info(self, ctrl: WL90Controller) -> None:
        assert ctrl.handle_notification(
            RESP_MUSIC_INFO, _packet(RESP_MUSIC_INFO, 8, 1, 20)
        )
        assert ctrl.music.volume == 8
        assert ctrl.music.sleep_timer_on
        assert ctrl.music.sleep_timer_minutes == 20
        ctrl.handle_notification(RESP_MUSIC_INFO, _packet(RESP_MUSIC_INFO, 8, 0, 20))
        assert ctrl.music.sleep_timer_minutes == 0

    @pytest.mark.parametrize("resp", [RESP_MUSIC_STATUS, RESP_MUSIC_TOGGLE])
    def test_music_status(self, ctrl: WL90Controller, resp: int) -> None:
        assert ctrl.handle_notification(resp, _packet(resp, 1, 0, 0))
        assert ctrl.music.is_on

    def test_music_short(self, ctrl: WL90Controller) -> None:
        assert ctrl.handle_notification(RESP_MUSIC_STATUS, _packet(RESP_MUSIC_STATUS))
        assert not ctrl.music.is_on

    def test_music_timer(self, ctrl: WL90Controller) -> None:
        assert ctrl.handle_notification(RESP_MUSIC_TIMER, _packet(RESP_MUSIC_TIMER, 1))
        assert ctrl.music.sleep_timer_on
        ctrl.handle_notification(RESP_MUSIC_TIMER, _packet(RESP_MUSIC_TIMER, 0))
        assert not ctrl.music.sleep_timer_on
        assert ctrl.handle_notification(
            RESP_MUSIC_TIMER, bytearray([0] * 7 + [RESP_MUSIC_TIMER])
        )

    def test_timer_end(self, ctrl: WL90Controller, instance: MagicMock) -> None:
        ctrl.radio.sleep_timer_on = True
        ctrl.music.sleep_timer_on = True
        assert ctrl.handle_notification(RESP_RADIO_TIMER_END, _packet(0))
        assert not ctrl.radio.sleep_timer_on
        instance.emit_lamp_event.assert_called_with(
            EVENT_TYPE_SLEEP_TIMER_FINISHED, {"timer": "radio"}
        )
        assert ctrl.handle_notification(RESP_MUSIC_TIMER_END, _packet(0))
        assert not ctrl.music.sleep_timer_on
        instance.emit_lamp_event.assert_called_with(
            EVENT_TYPE_SLEEP_TIMER_FINISHED, {"timer": "music"}
        )

    @pytest.mark.parametrize(
        "resp", [RESP_RADIO_POWER, RESP_RADIO_PRESET, RESP_RADIO_TUNE, RESP_RADIO_SAVE]
    )
    def test_radio_confirmations(self, ctrl: WL90Controller, resp: int) -> None:
        assert ctrl.handle_notification(resp, _packet(resp))
