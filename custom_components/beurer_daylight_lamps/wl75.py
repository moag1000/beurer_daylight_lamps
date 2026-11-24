"""WL75 Wake-up Light specific functionality.

This module handles WL75-specific features (Protocol 2):
- FM Radio (on/off, frequency, volume, presets, sleep timer)
- Alarms (2 slots with sunrise simulation)

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import (
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
    LOGGER,
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
from .exceptions import BeurerNotSupportedError
from .wl90 import AlarmItem, WL90Controller

if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance


class WL75Controller(WL90Controller):
    """Controller for WL75-specific features.

    WL75 uses protocol family 2 (different framing and opcodes than WL90/TL100):
    - 2 alarm slots (slot 0 -> ID 1, slot 1 -> ID 2)
    - FM radio (presets, seek/tune, volume, timer)
    - No Bluetooth speaker / music player
    """

    def __init__(self, instance: BeurerInstance) -> None:
        """Initialize WL75 controller."""
        super().__init__(instance)
        # WL75 has exactly 2 alarm slots (WL90 has 3)
        self.alarms = [
            AlarmItem(slot=0),
            AlarmItem(slot=1),
        ]

    # --- Radio Controls ---
    # Every command raises BeurerError if it could not be delivered; the
    # local state is only changed after the lamp received the command.

    async def radio_on(self) -> None:
        """Turn FM radio on."""
        LOGGER.info("Turning radio ON on WL75 %s", self._instance.mac)
        await self._instance.send_command([CMD_WL75_RADIO_POWER, 1])
        self.radio.is_on = True

    async def radio_off(self) -> None:
        """Turn FM radio off."""
        LOGGER.info("Turning radio OFF on WL75 %s", self._instance.mac)
        await self._instance.send_command([CMD_WL75_RADIO_POWER, 0])
        self.radio.is_on = False

    async def set_radio_volume(self, volume: int) -> None:
        """Set radio volume (0-10)."""
        volume = max(0, min(10, volume))
        LOGGER.debug(
            "Setting radio volume to %d on WL75 %s", volume, self._instance.mac
        )
        await self._instance.send_command([CMD_WL75_RADIO_VOLUME, volume])
        self.radio.volume = volume

    async def select_radio_preset(self, channel: int) -> None:
        """Select a radio preset channel (1-indexed, 1-10)."""
        channel = max(1, min(10, channel))
        LOGGER.debug(
            "Selecting radio preset %d on WL75 %s", channel, self._instance.mac
        )
        await self._instance.send_command([CMD_WL75_RADIO_CHANNEL, channel])
        self.radio.channel = channel - 1
        if len(self.radio.presets) >= channel:
            self.radio.frequency = self.radio.presets[channel - 1]

    async def radio_seek(self, direction: int = 1, auto_seek: bool = True) -> None:
        """Seek next radio station.

        Args:
            direction: 1 for next/up, 0 for previous/down.
            auto_seek: True for auto-seek search, False for fine-tuning.
        """
        cmd = CMD_WL75_RADIO_SEEK if auto_seek else CMD_WL75_RADIO_FINE_TUNE
        dir_byte = 0 if direction == 1 else 1  # 0=NEXT, 1=PREVIOUS in WL75Bytes
        LOGGER.debug(
            "WL75 Radio %s direction=%d on %s",
            "seek" if auto_seek else "tune",
            direction,
            self._instance.mac,
        )
        await self._instance.send_command([cmd, dir_byte])

    async def set_radio_sleep_timer(self, minutes: int) -> None:
        """Set radio sleep timer.

        Args:
            minutes: Timer duration (0 = disable, 1-60 = enable with duration).
        """
        if minutes == 0:
            await self._instance.send_command([CMD_WL75_RADIO_TIMER_TOGGLE, 0])
            self.radio.sleep_timer_on = False
            self.radio.sleep_timer_minutes = 0
            return
        await self._instance.send_command(
            [CMD_WL75_RADIO_TIMER_TOGGLE, 1], [CMD_WL75_RADIO_TIMER_VALUE, minutes]
        )
        self.radio.sleep_timer_on = True
        self.radio.sleep_timer_minutes = minutes

    async def save_radio_frequency(self, preset: int = 0) -> None:
        """Save current frequency to preset."""
        LOGGER.debug("Saving current frequency on WL75 %s", self._instance.mac)
        await self._instance.send_command([CMD_WL75_RADIO_SAVE_FREQ])

    async def query_radio_status(self) -> None:
        """Query radio status and presets 1-10."""
        LOGGER.debug("Querying radio status on WL75 %s", self._instance.mac)
        await self._instance.send_command(
            [CMD_WL75_RADIO_STATUS],
            [CMD_WL75_RADIO_PRESETS_1],
            [CMD_WL75_RADIO_PRESETS_2],
        )

    # --- Music/BT Speaker Controls (the WL75 has no BT speaker) ---

    async def music_on(self) -> None:
        """BT speaker is not supported on WL75."""
        raise BeurerNotSupportedError(self._instance.name)

    async def music_off(self) -> None:
        """BT speaker is not supported on WL75."""
        raise BeurerNotSupportedError(self._instance.name)

    async def set_music_volume(self, volume: int) -> None:
        """BT speaker is not supported on WL75."""
        raise BeurerNotSupportedError(self._instance.name)

    async def set_music_sleep_timer(self, minutes: int) -> None:
        """BT speaker is not supported on WL75."""
        raise BeurerNotSupportedError(self._instance.name)

    async def query_music_status(self) -> None:
        """BT speaker is not supported on WL75 (nothing to query)."""

    # --- Alarm Controls ---

    async def sync_alarm(self, slot: int, alarm: AlarmItem | None = None) -> None:
        """Sync an alarm to the device.

        Args:
            slot: Alarm slot (0 or 1).
            alarm: AlarmItem to sync.
        """
        if slot not in (0, 1):
            raise ValueError(f"Invalid alarm slot {slot} for WL75 (must be 0 or 1)")

        if alarm is None:
            alarm = self.alarms[slot]

        slot_id = slot + 1  # 1 or 2
        en_days = ((1 if alarm.enabled else 0) << 7) | (alarm.days & 0x7F)
        snooze_idx = alarm._snooze_to_index() + 1  # 1-based index (1-6)

        LOGGER.info(
            "Syncing WL75 alarm %d to %s: enabled=%s, %02d:%02d, days=%s",
            slot,
            self._instance.mac,
            alarm.enabled,
            alarm.hour,
            alarm.minute,
            alarm.days_list,
        )

        await self._instance.send_command(
            [
                CMD_WL75_ALARM_WRITE,
                slot_id,
                alarm.minute,
                alarm.hour,
                en_days,
                alarm.tone,
                alarm.volume,
                snooze_idx,
                0,  # wake_up
                alarm.sunrise_time,
                alarm.sunrise_brightness,
            ]
        )
        self.alarms[slot] = alarm

    # --- Notification Handling ---

    def handle_notification(  # noqa: PLR0911
        self, resp_cmd: int, payload: bytearray
    ) -> bool:
        """Handle WL75 radio and alarm response payloads.

        Args:
            resp_cmd: Response opcode (payload[0]).
            payload: Resolved payload bytes without framing.

        Returns:
            True if handled, False otherwise.
        """
        if resp_cmd == RESP_WL75_RADIO_STATUS:
            self._parse_radio_status(payload)
            return True

        if resp_cmd == RESP_WL75_RADIO_PRESETS_1:
            self._parse_radio_presets(1, payload)
            return True

        if resp_cmd == RESP_WL75_RADIO_PRESETS_2:
            self._parse_radio_presets(2, payload)
            return True

        if resp_cmd in (RESP_WL75_RADIO_SEARCH, RESP_WL75_RADIO_FINE_TUNE):
            if len(payload) >= 4:
                self.radio.frequency = (payload[2] << 8) | payload[3]
                LOGGER.debug(
                    "WL75 Radio frequency tuned to: %.1f MHz", self.radio.frequency_mhz
                )
            return True

        if resp_cmd == RESP_WL75_ALARM:
            self._parse_alarm_response(payload)
            return True

        if resp_cmd in (
            RESP_WL75_RADIO_POWER,
            RESP_WL75_RADIO_CHANNEL,
            RESP_WL75_RADIO_VOLUME,
            RESP_WL75_RADIO_SLEEP_TIMER_ENABLE,
            RESP_WL75_RADIO_SLEEP_TIMER_VALUE,
            RESP_WL75_SAVE_RADIO_FREQ,
            RESP_WL75_UPDATE_ALARM,
        ):
            LOGGER.debug(
                "WL75 ACK response 0x%02X from %s", resp_cmd, self._instance.mac
            )
            return True

        return False

    def _parse_radio_status(self, payload: bytearray) -> None:
        """Parse WL75 radio status payload."""
        if len(payload) < 8:
            return
        self.radio.is_on = payload[1] == 1
        self.radio.channel = max(0, payload[2] - 1)
        self.radio.frequency = (payload[3] << 8) | payload[4]
        self.radio.volume = min(10, payload[5])
        self.radio.sleep_timer_on = payload[6] == 1
        self.radio.sleep_timer_minutes = (
            max(1, payload[7]) if self.radio.sleep_timer_on else 0
        )
        LOGGER.debug(
            "WL75 Radio status: on=%s, ch=%d, freq=%.1f MHz, vol=%d, timer=%s/%d",
            self.radio.is_on,
            self.radio.channel,
            self.radio.frequency_mhz,
            self.radio.volume,
            self.radio.sleep_timer_on,
            self.radio.sleep_timer_minutes,
        )

    def _parse_radio_presets(self, part: int, payload: bytearray) -> None:
        """Parse WL75 radio presets (part 1: presets 1-5, part 2: presets 6-10)."""
        presets = list(self.radio.presets)
        if len(presets) < 10:
            presets = [0] * 10

        start_idx = 0 if part == 1 else 5
        for i in range(5):
            idx = 1 + (i * 2)
            if idx + 1 < len(payload):
                freq = (payload[idx] << 8) | payload[idx + 1]
                presets[start_idx + i] = freq

        self.radio.presets = presets
        LOGGER.debug("WL75 Radio presets part %d: %s", part, presets)

    def _parse_alarm_response(self, payload: bytearray) -> None:
        """Parse WL75 alarm info response."""
        if len(payload) < 11:
            return

        slot_raw = payload[1] & 0x7F
        slot = slot_raw - 1
        if slot not in (0, 1):
            return

        alarm = self.alarms[slot]
        alarm.minute = payload[2]
        alarm.hour = payload[3]
        b2 = payload[4]
        alarm.enabled = bool((b2 & 0x80) >> 7)
        alarm.days = b2 & 0x7F
        alarm.tone = payload[5]
        alarm.volume = payload[6]
        snooze_raw = payload[7]
        snooze_idx = max(0, min(5, snooze_raw - 1))
        alarm.snooze_minutes = AlarmItem.SNOOZE_MAP[snooze_idx]
        alarm.sunrise_time = payload[9]
        alarm.sunrise_brightness = payload[10]
        alarm.sunrise_enabled = alarm.sunrise_time > 0 or alarm.sunrise_brightness > 0

        LOGGER.debug(
            "WL75 Alarm %d: enabled=%s, %02d:%02d, days=0x%02X, tone=%d, vol=%d, snooze=%d min",
            slot,
            alarm.enabled,
            alarm.hour,
            alarm.minute,
            alarm.days,
            alarm.tone,
            alarm.volume,
            alarm.snooze_minutes,
        )
