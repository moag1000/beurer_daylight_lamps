"""Tests for the WL radio and Bluetooth speaker media players."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import MediaPlayerState, MediaType

from custom_components.beurer_daylight_lamps.media_player import (
    BeurerMusicPlayer,
    BeurerRadioPlayer,
    async_setup_entry,
)
from custom_components.beurer_daylight_lamps.wl90 import MusicState, RadioState


@pytest.fixture
def wl90() -> MagicMock:
    """Return a fake WL90 controller."""
    ctrl = MagicMock()
    ctrl.radio = RadioState(is_on=True, frequency=1040, volume=4, channel=2)
    ctrl.music = MusicState(is_on=False, volume=6)
    for name in (
        "radio_on",
        "radio_off",
        "set_radio_volume",
        "radio_seek",
        "music_on",
        "music_off",
        "set_music_volume",
    ):
        setattr(ctrl, name, AsyncMock(return_value=True))
    return ctrl


@pytest.fixture
def coordinator(wl90: MagicMock) -> MagicMock:
    """Return a coordinator whose instance is a WL90."""
    coord = MagicMock()
    coord.instance.mac = "AA:BB:CC:DD:EE:FF"
    coord.instance.available = True
    coord.instance.wl90 = wl90
    return coord


async def test_setup_entry_models() -> None:
    """Radio for every WL, speaker only for WL90, nothing for TL."""
    entry = MagicMock()
    entry.data = {"name": "WL90_1234"}
    add = MagicMock()

    entry.runtime_data.instance.is_wl = False
    await async_setup_entry(MagicMock(), entry, add)
    add.assert_not_called()

    entry.runtime_data.instance.is_wl = True
    entry.runtime_data.instance.is_wl90 = False
    await async_setup_entry(MagicMock(), entry, add)
    assert [type(e) for e in add.call_args.args[0]] == [BeurerRadioPlayer]

    entry.runtime_data.instance.is_wl90 = True
    await async_setup_entry(MagicMock(), entry, add)
    assert [type(e) for e in add.call_args.args[0]] == [
        BeurerRadioPlayer,
        BeurerMusicPlayer,
    ]


class TestRadioPlayer:
    """FM radio entity."""

    def test_properties(self, coordinator: MagicMock) -> None:
        player = BeurerRadioPlayer(coordinator, "WL90_1234")
        assert player.unique_id == "aa:bb:cc:dd:ee:ff_radio"
        assert player.state == MediaPlayerState.PLAYING
        assert player.volume_level == 0.4
        assert player.media_content_type == MediaType.CHANNEL
        assert player.media_title == "104.0 MHz"
        assert player.extra_state_attributes == {
            "channel": 2,
            "frequency_mhz": 104.0,
            "sleep_timer_on": False,
            "sleep_timer_minutes": 0,
        }
        assert player.available
        info = player.device_info
        assert info["manufacturer"] == "Beurer"
        assert info["name"] == "WL90_1234"

    def test_idle_and_unavailable(self, coordinator: MagicMock) -> None:
        player = BeurerRadioPlayer(coordinator, "WL90")
        coordinator.instance.wl90.radio.is_on = False
        assert player.state == MediaPlayerState.IDLE
        assert player.media_title is None
        coordinator.instance.available = False
        assert player.state == MediaPlayerState.OFF
        assert not player.available

    def test_without_controller(self, coordinator: MagicMock) -> None:
        coordinator.instance.wl90 = None
        player = BeurerRadioPlayer(coordinator, "WL90")
        assert player.state == MediaPlayerState.IDLE
        assert player.volume_level is None
        assert player.media_title is None
        assert player.extra_state_attributes is None

    async def test_commands(self, coordinator: MagicMock, wl90: MagicMock) -> None:
        player = BeurerRadioPlayer(coordinator, "WL90")
        await player.async_turn_on()
        wl90.radio_on.assert_awaited_once()
        await player.async_turn_off()
        wl90.radio_off.assert_awaited_once()
        await player.async_set_volume_level(0.7)
        wl90.set_radio_volume.assert_awaited_with(7)
        await player.async_volume_up()
        wl90.set_radio_volume.assert_awaited_with(5)
        await player.async_volume_down()
        wl90.set_radio_volume.assert_awaited_with(3)
        wl90.radio.volume = 10
        await player.async_volume_up()
        wl90.set_radio_volume.assert_awaited_with(10)
        wl90.radio.volume = 0
        await player.async_volume_down()
        wl90.set_radio_volume.assert_awaited_with(0)
        await player.async_media_next_track()
        wl90.radio_seek.assert_awaited_with(1)
        await player.async_media_previous_track()
        wl90.radio_seek.assert_awaited_with(0)

    async def test_commands_without_controller(self, coordinator: MagicMock) -> None:
        coordinator.instance.wl90 = None
        player = BeurerRadioPlayer(coordinator, "WL90")
        await player.async_turn_on()
        await player.async_turn_off()
        await player.async_set_volume_level(0.5)
        await player.async_volume_up()
        await player.async_volume_down()
        await player.async_media_next_track()
        await player.async_media_previous_track()


class TestMusicPlayer:
    """Bluetooth speaker entity."""

    def test_properties(self, coordinator: MagicMock) -> None:
        player = BeurerMusicPlayer(coordinator, "WL90_1234")
        assert player.unique_id == "aa:bb:cc:dd:ee:ff_music"
        assert player.state == MediaPlayerState.IDLE
        assert player.volume_level == 0.6
        assert player.extra_state_attributes == {
            "sleep_timer_on": False,
            "sleep_timer_minutes": 0,
        }
        assert player.available
        assert player.device_info["model"]
        coordinator.instance.wl90.music.is_on = True
        assert player.state == MediaPlayerState.PLAYING
        coordinator.instance.available = False
        assert player.state == MediaPlayerState.OFF

    def test_without_controller(self, coordinator: MagicMock) -> None:
        coordinator.instance.wl90 = None
        player = BeurerMusicPlayer(coordinator, "WL90")
        assert player.state == MediaPlayerState.IDLE
        assert player.volume_level is None
        assert player.extra_state_attributes is None

    async def test_commands(self, coordinator: MagicMock, wl90: MagicMock) -> None:
        player = BeurerMusicPlayer(coordinator, "WL90")
        await player.async_turn_on()
        wl90.music_on.assert_awaited_once()
        await player.async_turn_off()
        wl90.music_off.assert_awaited_once()
        await player.async_set_volume_level(0.3)
        wl90.set_music_volume.assert_awaited_with(3)
        await player.async_volume_up()
        wl90.set_music_volume.assert_awaited_with(7)
        await player.async_volume_down()
        wl90.set_music_volume.assert_awaited_with(5)

    async def test_commands_without_controller(self, coordinator: MagicMock) -> None:
        coordinator.instance.wl90 = None
        player = BeurerMusicPlayer(coordinator, "WL90")
        await player.async_turn_on()
        await player.async_turn_off()
        await player.async_set_volume_level(0.5)
        await player.async_volume_up()
        await player.async_volume_down()
