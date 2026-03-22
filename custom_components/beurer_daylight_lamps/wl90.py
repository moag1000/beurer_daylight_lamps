"""WL90 Wake-up Light specific functionality.

This module handles WL90-specific features that are not present on TL models:
- FM Radio (on/off, frequency, volume, presets, sleep timer)
- Alarms (3 slots with sunrise simulation)
- Bluetooth Speaker (on/off, volume, sleep timer)

Protocol details discovered from APK reverse engineering of Beurer LightUp 2.1.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .const import (
    LOGGER,
    ALARM_SLOT_MAP,
    CMD_ALARM_SYNC,
    CMD_RADIO_POWER,
    CMD_RADIO_VOLUME,
    CMD_RADIO_PRESET,
    CMD_RADIO_TUNE,
    CMD_RADIO_TIMER_TOGGLE,
    CMD_RADIO_TIMER_VALUE,
    CMD_RADIO_SAVE_FREQ,
    CMD_RADIO_SYNC_STATUS,
    CMD_MUSIC_TOGGLE,
    CMD_MUSIC_VOLUME,
    CMD_MUSIC_TIMER_TOGGLE,
    CMD_MUSIC_TIMER_VALUE,
    CMD_MUSIC_QUERY,
    CMD_MUSIC_CLOSE,
    COMMAND_DELAY,
    RESP_ALARM,
    RESP_RADIO_STATUS,
    RESP_RADIO_INFO,
    RESP_MUSIC_STATUS,
    RESP_MUSIC_INFO,
    RESP_MUSIC_TOGGLE,
    RESP_MUSIC_TIMER,
    RESP_RADIO_TIMER_END,
    RESP_MUSIC_TIMER_END,
    RESP_RADIO_POWER,
    RESP_RADIO_PRESET,
    RESP_RADIO_TUNE,
    RESP_RADIO_SAVE,
)

if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance


@dataclass
class AlarmItem:
    """Represents a single alarm slot on the WL90.

    The WL90 has 3 alarm slots, each with full configuration
    including sunrise simulation.
    """

    slot: int = 0              # 0, 1, or 2
    enabled: bool = False
    hour: int = 7
    minute: int = 0
    # Weekday bitmask: bit0=Sun, bit1=Mon, ..., bit6=Sat
    days: int = 0x3E           # Default: Mon-Fri (0b0111110)
    tone: int = 0              # Alarm tone index (0-11)
    volume: int = 5            # Volume 0-10
    snooze_minutes: int = 10   # Snooze duration in minutes (user-facing)
    sunrise_enabled: bool = True
    sunrise_time: int = 20     # Minutes before alarm for sunrise start
    sunrise_brightness: int = 50  # Sunrise max brightness %

    # Snooze protocol mapping: the device uses an INDEX (0-5), not minutes
    SNOOZE_MAP: tuple[int, ...] = (1, 2, 5, 10, 20, 30)  # index -> minutes

    def _snooze_to_index(self) -> int:
        """Convert snooze_minutes to protocol index (0-5)."""
        # Find closest match
        for i, minutes in enumerate(self.SNOOZE_MAP):
            if self.snooze_minutes <= minutes:
                return i
        return 5  # 30 min (max)

    @staticmethod
    def _snooze_from_index(index: int) -> int:
        """Convert protocol index (0-5) to minutes."""
        snooze_values = (1, 2, 5, 10, 20, 30)
        if 0 <= index < len(snooze_values):
            return snooze_values[index]
        return 10  # Default

    @property
    def days_list(self) -> list[str]:
        """Return human-readable list of active days."""
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        return [day_names[i] for i in range(7) if self.days & (1 << i)]

    @days_list.setter
    def days_list(self, days: list[str]) -> None:
        """Set days from a list of day name strings."""
        day_map = {"Sun": 0, "Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6}
        self.days = 0
        for day in days:
            if day in day_map:
                self.days |= (1 << day_map[day])


@dataclass
class RadioState:
    """Represents the FM radio state of the WL90."""

    is_on: bool = False
    channel: int = 0          # Current preset channel (0-indexed)
    frequency: int = 0        # Frequency in 10kHz units (e.g., 1040 = 104.0 MHz)
    volume: int = 5           # Volume 0-10
    sleep_timer_on: bool = False
    sleep_timer_minutes: int = 0
    presets: list[int] = field(default_factory=list)  # Saved frequencies

    @property
    def frequency_mhz(self) -> float:
        """Return frequency in MHz."""
        return self.frequency / 10.0 if self.frequency else 0.0


@dataclass
class MusicState:
    """Represents the Bluetooth speaker state of the WL90."""

    is_on: bool = False
    volume: int = 5           # Volume 0-10
    sleep_timer_on: bool = False
    sleep_timer_minutes: int = 0


class WL90Controller:
    """Controller for WL90-specific features.

    This class manages radio, alarm, and music functionality
    that is exclusive to the WL90 Wake-up Light model.
    """

    def __init__(self, instance: BeurerInstance) -> None:
        """Initialize WL90 controller.

        Args:
            instance: The parent BeurerInstance for BLE communication.
        """
        self._instance = instance
        self.radio = RadioState()
        self.music = MusicState()
        self.alarms: list[AlarmItem] = [
            AlarmItem(slot=0),
            AlarmItem(slot=1),
            AlarmItem(slot=2),
        ]

    # --- Radio Controls ---

    async def radio_on(self) -> bool:
        """Turn FM radio on."""
        LOGGER.info("Turning radio ON on %s", self._instance.mac)
        result = await self._instance._send_packet([CMD_RADIO_POWER, 1])
        if result:
            self.radio.is_on = True
        return result

    async def radio_off(self) -> bool:
        """Turn FM radio off."""
        LOGGER.info("Turning radio OFF on %s", self._instance.mac)
        result = await self._instance._send_packet([CMD_RADIO_POWER, 0])
        if result:
            self.radio.is_on = False
        return result

    async def set_radio_volume(self, volume: int) -> bool:
        """Set radio volume (0-10)."""
        volume = max(0, min(10, volume))
        LOGGER.debug("Setting radio volume to %d on %s", volume, self._instance.mac)
        result = await self._instance._send_packet([CMD_RADIO_VOLUME, volume])
        if result:
            self.radio.volume = volume
        return result

    async def select_radio_preset(self, channel: int) -> bool:
        """Select a radio preset channel (1-indexed, 1-10)."""
        channel = max(1, min(10, channel))
        LOGGER.debug("Selecting radio preset %d on %s", channel, self._instance.mac)
        result = await self._instance._send_packet([CMD_RADIO_PRESET, channel])
        if result:
            self.radio.channel = channel
        return result

    async def radio_seek(self, direction: int = 1, auto_seek: bool = True) -> bool:
        """Seek next radio station.

        Args:
            direction: 1 for seek up, 0 for seek down.
            auto_seek: True for auto-seek (find next station), False for fine-tune (step).
        """
        tune_type = 1 if auto_seek else 0
        LOGGER.debug("Radio seek type=%d direction=%d on %s", tune_type, direction, self._instance.mac)
        return await self._instance._send_packet([CMD_RADIO_TUNE, tune_type, direction])

    async def set_radio_sleep_timer(self, minutes: int) -> bool:
        """Set radio sleep timer.

        Args:
            minutes: Timer duration (0 = disable, 1-120 = enable with duration).
        """
        if minutes == 0:
            result = await self._instance._send_packet([CMD_RADIO_TIMER_TOGGLE, 0])
            if result:
                self.radio.sleep_timer_on = False
            return result

        result = await self._instance._send_packet([CMD_RADIO_TIMER_TOGGLE, 1])
        if result:
            await asyncio.sleep(COMMAND_DELAY)
            result = await self._instance._send_packet([CMD_RADIO_TIMER_VALUE, minutes])
            if result:
                self.radio.sleep_timer_on = True
                self.radio.sleep_timer_minutes = minutes
        return result

    async def save_radio_frequency(self, preset: int) -> bool:
        """Save current frequency to a preset slot."""
        LOGGER.debug("Saving frequency to preset %d on %s", preset, self._instance.mac)
        return await self._instance._send_packet([CMD_RADIO_SAVE_FREQ, preset])

    async def query_radio_status(self) -> bool:
        """Query current radio status."""
        return await self._instance._send_packet([CMD_RADIO_SYNC_STATUS])

    # --- Music/BT Speaker Controls ---

    async def music_on(self) -> bool:
        """Turn Bluetooth speaker on."""
        LOGGER.info("Turning BT speaker ON on %s", self._instance.mac)
        result = await self._instance._send_packet([CMD_MUSIC_TOGGLE, 1])
        if result:
            self.music.is_on = True
        return result

    async def music_off(self) -> bool:
        """Turn Bluetooth speaker off."""
        LOGGER.info("Turning BT speaker OFF on %s", self._instance.mac)
        result = await self._instance._send_packet([CMD_MUSIC_CLOSE])
        if result:
            self.music.is_on = False
        return result

    async def set_music_volume(self, volume: int) -> bool:
        """Set music/speaker volume (0-10)."""
        volume = max(0, min(10, volume))
        LOGGER.debug("Setting music volume to %d on %s", volume, self._instance.mac)
        result = await self._instance._send_packet([CMD_MUSIC_VOLUME, volume])
        if result:
            self.music.volume = volume
        return result

    async def set_music_sleep_timer(self, minutes: int) -> bool:
        """Set music sleep timer."""
        if minutes == 0:
            result = await self._instance._send_packet([CMD_MUSIC_TIMER_TOGGLE, 0])
            if result:
                self.music.sleep_timer_on = False
            return result

        result = await self._instance._send_packet([CMD_MUSIC_TIMER_TOGGLE, 1])
        if result:
            await asyncio.sleep(COMMAND_DELAY)
            result = await self._instance._send_packet([CMD_MUSIC_TIMER_VALUE, minutes])
            if result:
                self.music.sleep_timer_on = True
                self.music.sleep_timer_minutes = minutes
        return result

    async def query_music_status(self) -> bool:
        """Query current music/speaker status."""
        return await self._instance._send_packet([CMD_MUSIC_QUERY])

    # --- Alarm Controls ---

    async def sync_alarm(self, slot: int, alarm: AlarmItem | None = None) -> bool:
        """Sync an alarm to the device.

        Args:
            slot: Alarm slot (0, 1, or 2).
            alarm: AlarmItem to sync. If None, uses the stored alarm for this slot.
        """
        if slot not in ALARM_SLOT_MAP:
            LOGGER.error("Invalid alarm slot %d (must be 0, 1, or 2)", slot)
            return False

        if alarm is None:
            alarm = self.alarms[slot]

        direction_byte = ALARM_SLOT_MAP[slot]

        LOGGER.info(
            "Syncing alarm %d to %s: enabled=%s, %02d:%02d, days=%s",
            slot, self._instance.mac, alarm.enabled,
            alarm.hour, alarm.minute, alarm.days_list,
        )

        result = await self._instance._send_packet([
            CMD_ALARM_SYNC,
            direction_byte,
            1 if alarm.enabled else 0,
            alarm.minute,
            alarm.hour,
            alarm.days,
            alarm.tone,
            alarm.volume,
            alarm._snooze_to_index(),  # Protocol uses index (0-5), not minutes
            1 if alarm.sunrise_enabled else 0,
            alarm.sunrise_time,
            alarm.sunrise_brightness,
        ])

        if result:
            self.alarms[slot] = alarm

        return result

    # --- Notification Handling ---

    def handle_notification(self, resp_cmd: int, data: bytearray) -> bool:
        """Handle WL90-specific notification responses.

        Args:
            resp_cmd: Response command byte (data[7]).
            data: Full notification data.

        Returns:
            True if the notification was handled, False if not a WL90 response.
        """
        if resp_cmd == RESP_RADIO_STATUS:
            self._parse_radio_status(data)
            return True
        elif resp_cmd == RESP_RADIO_INFO:
            self._parse_radio_info(data)
            return True
        elif resp_cmd == RESP_ALARM:
            self._parse_alarm_response(data)
            return True
        elif resp_cmd in (RESP_MUSIC_STATUS, RESP_MUSIC_INFO, RESP_MUSIC_TOGGLE):
            self._parse_music_response(resp_cmd, data)
            return True
        elif resp_cmd == RESP_MUSIC_TIMER:
            self._parse_music_timer(data)
            return True
        elif resp_cmd in (RESP_RADIO_TIMER_END, RESP_MUSIC_TIMER_END):
            timer_type = "radio" if resp_cmd == RESP_RADIO_TIMER_END else "music"
            LOGGER.info("WL90 %s timer ended on %s", timer_type, self._instance.mac)
            if resp_cmd == RESP_RADIO_TIMER_END:
                self.radio.sleep_timer_on = False
            else:
                self.music.sleep_timer_on = False
            return True

        # Radio confirmation responses (must be caught to prevent
        # fall-through to version-based status routing which would corrupt state)
        if resp_cmd == RESP_RADIO_POWER:
            # Radio power toggle confirmation - request fresh status
            LOGGER.debug("Radio power confirmation from %s", self._instance.mac)
            return True
        elif resp_cmd == RESP_RADIO_PRESET:
            LOGGER.debug("Radio preset confirmation from %s", self._instance.mac)
            return True
        elif resp_cmd == RESP_RADIO_TUNE:
            LOGGER.debug("Radio tune/seek confirmation from %s", self._instance.mac)
            return True
        elif resp_cmd == RESP_RADIO_SAVE:
            LOGGER.debug("Radio frequency save confirmation from %s", self._instance.mac)
            return True

        return False

    def _parse_radio_status(self, data: bytearray) -> None:
        """Parse radio status response."""
        if len(data) < 15:
            return
        self.radio.is_on = data[8] == 1
        self.radio.channel = data[9]
        self.radio.frequency = (data[10] << 8) | data[11]
        self.radio.volume = min(10, data[12])
        self.radio.sleep_timer_on = data[13] == 1
        self.radio.sleep_timer_minutes = max(1, data[14]) if self.radio.sleep_timer_on else 0

        LOGGER.debug(
            "Radio status: on=%s, ch=%d, freq=%.1f MHz, vol=%d, timer=%s/%d",
            self.radio.is_on, self.radio.channel,
            self.radio.frequency_mhz, self.radio.volume,
            self.radio.sleep_timer_on, self.radio.sleep_timer_minutes,
        )

    def _parse_radio_info(self, data: bytearray) -> None:
        """Parse radio preset info response."""
        if len(data) < 10:
            return
        # Radio info responses contain frequency data for presets
        LOGGER.debug("Radio info from %s: %s", self._instance.mac, data.hex())

    def _parse_alarm_response(self, data: bytearray) -> None:
        """Parse alarm data response."""
        if len(data) < 19:
            return

        # Determine alarm slot from direction byte
        direction = data[8]
        index = direction & 0x7F

        slot = {1: 0, 7: 1, 3: 2}.get(index)
        if slot is None:
            LOGGER.debug("Unknown alarm index %d", index)
            return

        alarm = self.alarms[slot]
        alarm.enabled = data[9] == 1
        alarm.hour = data[10]
        alarm.minute = data[11]
        alarm.days = data[12]
        alarm.tone = data[13]
        alarm.volume = data[14]
        alarm.snooze_minutes = AlarmItem._snooze_from_index(data[15])  # Convert index back to minutes
        alarm.sunrise_enabled = data[16] == 1
        alarm.sunrise_time = data[17]
        alarm.sunrise_brightness = data[18]

        LOGGER.debug(
            "Alarm %d: enabled=%s, %02d:%02d, days=%s, sunrise=%s",
            slot, alarm.enabled, alarm.hour, alarm.minute,
            alarm.days_list, alarm.sunrise_enabled,
        )

    def _parse_music_response(self, resp_cmd: int, data: bytearray) -> None:
        """Parse music/speaker status response."""
        if len(data) < 11:
            return

        if resp_cmd == RESP_MUSIC_INFO:
            self.music.volume = data[8]
            self.music.sleep_timer_on = data[9] == 1
            self.music.sleep_timer_minutes = data[10] if self.music.sleep_timer_on else 0
        elif resp_cmd in (RESP_MUSIC_STATUS, RESP_MUSIC_TOGGLE):
            self.music.is_on = data[8] == 1

        LOGGER.debug(
            "Music status: on=%s, vol=%d, timer=%s/%d",
            self.music.is_on, self.music.volume,
            self.music.sleep_timer_on, self.music.sleep_timer_minutes,
        )

    def _parse_music_timer(self, data: bytearray) -> None:
        """Parse music timer confirmation."""
        if len(data) < 9:
            return
        self.music.sleep_timer_on = data[8] == 1
        LOGGER.debug("Music timer: %s", "on" if self.music.sleep_timer_on else "off")
