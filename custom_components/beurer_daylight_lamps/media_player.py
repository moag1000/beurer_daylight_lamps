"""Media player platform for Beurer WL90 Wake-up Light.

Provides media player entities for WL90-specific features:
- FM Radio with preset channels
- Bluetooth Speaker for music playback

These entities are only created for WL90 devices (not TL models).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BeurerConfigEntry
from .const import DOMAIN, LOGGER, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer media player entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    instance = entry.runtime_data.instance
    name = entry.data.get("name", "Beurer Lamp")

    # Only add media player entities for WL90 devices
    if not instance.is_wl90:
        return

    entities: list[MediaPlayerEntity] = [
        BeurerRadioPlayer(coordinator, name),
        BeurerMusicPlayer(coordinator, name),
    ]
    async_add_entities(entities)


class BeurerRadioPlayer(
    CoordinatorEntity[BeurerDataUpdateCoordinator], MediaPlayerEntity
):
    """FM Radio media player for WL90."""

    _attr_has_entity_name = True
    _attr_translation_key = "fm_radio"
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize the radio player."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_radio"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the radio."""
        if not self._instance.available:
            return MediaPlayerState.OFF
        wl90 = self._instance.wl90
        if wl90 and wl90.radio.is_on:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return volume level (0.0 to 1.0)."""
        wl90 = self._instance.wl90
        if wl90:
            return wl90.radio.volume / 10.0
        return None

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Return the content type."""
        return MediaType.CHANNEL

    @property
    def media_title(self) -> str | None:
        """Return current station info."""
        wl90 = self._instance.wl90
        if wl90 and wl90.radio.is_on:
            return f"{wl90.radio.frequency_mhz:.1f} MHz"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        wl90 = self._instance.wl90
        if not wl90:
            return None
        return {
            "channel": wl90.radio.channel,
            "frequency_mhz": wl90.radio.frequency_mhz,
            "sleep_timer_on": wl90.radio.sleep_timer_on,
            "sleep_timer_minutes": wl90.radio.sleep_timer_minutes,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        mac = format_mac(self._instance.mac)
        return DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=detect_model(self._device_name),
            sw_version=VERSION,
            connections={(CONNECTION_BLUETOOTH, mac)},
        )

    async def async_turn_on(self) -> None:
        """Turn on the radio."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.radio_on()

    async def async_turn_off(self) -> None:
        """Turn off the radio."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.radio_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.set_radio_volume(int(volume * 10))

    async def async_volume_up(self) -> None:
        """Volume up."""
        wl90 = self._instance.wl90
        if wl90:
            new_vol = min(10, wl90.radio.volume + 1)
            await wl90.set_radio_volume(new_vol)

    async def async_volume_down(self) -> None:
        """Volume down."""
        wl90 = self._instance.wl90
        if wl90:
            new_vol = max(0, wl90.radio.volume - 1)
            await wl90.set_radio_volume(new_vol)

    async def async_media_next_track(self) -> None:
        """Seek to next station."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.radio_seek(1)

    async def async_media_previous_track(self) -> None:
        """Seek to previous station."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.radio_seek(0)


class BeurerMusicPlayer(
    CoordinatorEntity[BeurerDataUpdateCoordinator], MediaPlayerEntity
):
    """Bluetooth Speaker media player for WL90."""

    _attr_has_entity_name = True
    _attr_translation_key = "bt_speaker"
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize the music player."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_music"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the speaker."""
        if not self._instance.available:
            return MediaPlayerState.OFF
        wl90 = self._instance.wl90
        if wl90 and wl90.music.is_on:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return volume level (0.0 to 1.0)."""
        wl90 = self._instance.wl90
        if wl90:
            return wl90.music.volume / 10.0
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        wl90 = self._instance.wl90
        if not wl90:
            return None
        return {
            "sleep_timer_on": wl90.music.sleep_timer_on,
            "sleep_timer_minutes": wl90.music.sleep_timer_minutes,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        mac = format_mac(self._instance.mac)
        return DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=detect_model(self._device_name),
            sw_version=VERSION,
            connections={(CONNECTION_BLUETOOTH, mac)},
        )

    async def async_turn_on(self) -> None:
        """Turn on the speaker."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.music_on()

    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.music_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        wl90 = self._instance.wl90
        if wl90:
            await wl90.set_music_volume(int(volume * 10))

    async def async_volume_up(self) -> None:
        """Volume up."""
        wl90 = self._instance.wl90
        if wl90:
            new_vol = min(10, wl90.music.volume + 1)
            await wl90.set_music_volume(new_vol)

    async def async_volume_down(self) -> None:
        """Volume down."""
        wl90 = self._instance.wl90
        if wl90:
            new_vol = max(0, wl90.music.volume - 1)
            await wl90.set_music_volume(new_vol)
