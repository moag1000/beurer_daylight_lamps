"""Extra coverage for number entities (WL volumes, timer, durations)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.beurer_daylight_lamps.number import (
    WL90_NUMBER_DESCRIPTIONS,
    BeurerSimulationDurationNumber,
    BeurerTimerNumber,
    BeurerWL90Number,
    async_setup_entry,
)
from custom_components.beurer_daylight_lamps.therapy import SimulationSettings
from custom_components.beurer_daylight_lamps.wl90 import MusicState, RadioState


def _desc(key: str):
    return next(d for d in WL90_NUMBER_DESCRIPTIONS if d.key == key)


@pytest.fixture
def coordinator() -> MagicMock:
    """Return a coordinator with a fake WL90 instance."""
    coord = MagicMock()
    inst = coord.instance
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst.available = True
    inst.wl90 = MagicMock()
    inst.wl90.radio = RadioState(volume=3)
    inst.wl90.music = MusicState(volume=8)
    inst.wl90.set_radio_volume = AsyncMock()
    inst.wl90.set_music_volume = AsyncMock()
    return coord


@pytest.mark.parametrize(
    ("is_wl", "is_wl90", "keys"),
    [
        (False, False, set()),
        (True, False, {"radio_volume"}),
        (True, True, {"radio_volume", "music_volume"}),
    ],
)
async def test_setup_wl_volumes(
    coordinator: MagicMock, is_wl: bool, is_wl90: bool, keys: set[str]
) -> None:
    entry = MagicMock()
    entry.data = {"name": "WL"}
    entry.runtime_data.coordinator = coordinator
    entry.runtime_data.instance.is_wl = is_wl
    entry.runtime_data.instance.is_wl90 = is_wl90
    add = MagicMock()
    await async_setup_entry(MagicMock(), entry, add)
    found = {
        e.entity_description.key
        for e in add.call_args.args[0]
        if isinstance(e, BeurerWL90Number)
    }
    assert found == keys


class TestWL90Number:
    """Radio and speaker volumes."""

    async def test_radio(self, coordinator: MagicMock) -> None:
        num = BeurerWL90Number(coordinator, "WL90", _desc("radio_volume"))
        assert num.native_value == 3
        assert num.available
        assert num.device_info["name"] == "WL90"
        await num.async_set_native_value(6.0)
        coordinator.instance.wl90.set_radio_volume.assert_awaited_with(6)

    async def test_music(self, coordinator: MagicMock) -> None:
        num = BeurerWL90Number(coordinator, "WL90", _desc("music_volume"))
        assert num.native_value == 8
        await num.async_set_native_value(2.0)
        coordinator.instance.wl90.set_music_volume.assert_awaited_with(2)

    async def test_unknown_key_and_no_controller(self, coordinator: MagicMock) -> None:
        desc = MagicMock()
        desc.key = "other"
        num = BeurerWL90Number(coordinator, "WL90", desc)
        assert num.native_value is None
        await num.async_set_native_value(1)
        coordinator.instance.wl90 = None
        assert num.native_value is None
        await num.async_set_native_value(1)


class TestTimerNumber:
    """Timer cancel path."""

    async def test_cancel(self, coordinator: MagicMock) -> None:
        coordinator.instance.cancel_timer = AsyncMock(return_value=True)
        timer = BeurerTimerNumber(coordinator, "TL100")
        await timer.async_set_native_value(0)
        coordinator.instance.cancel_timer.assert_awaited_once()

    async def test_cancel_fails(self, coordinator: MagicMock) -> None:
        coordinator.instance.cancel_timer = AsyncMock(return_value=False)
        timer = BeurerTimerNumber(coordinator, "TL100")
        with pytest.raises(HomeAssistantError):
            await timer.async_set_native_value(0)


class TestSimulationDuration:
    """Sunrise / sunset durations."""

    async def test_set_and_read(self, coordinator: MagicMock) -> None:
        coordinator.instance.simulation_settings = SimulationSettings()
        sunrise = BeurerSimulationDurationNumber(
            coordinator, "TL100", "sunrise_duration"
        )
        sunset = BeurerSimulationDurationNumber(coordinator, "TL100", "sunset_duration")
        sunrise.async_write_ha_state = MagicMock()
        assert sunrise.available
        assert sunrise.device_info["manufacturer"] == "Beurer"
        await sunrise.async_set_native_value(25.0)
        assert coordinator.instance.simulation_settings.sunrise_minutes == 25
        assert sunrise.native_value == 25.0
        assert sunset.native_value == float(
            coordinator.instance.simulation_settings.sunset_minutes
        )

    @pytest.mark.parametrize("restored", [None, 42.0])
    async def test_restore(self, coordinator: MagicMock, restored) -> None:
        settings = SimulationSettings()
        default = settings.sunset_minutes
        coordinator.instance.simulation_settings = settings
        num = BeurerSimulationDurationNumber(coordinator, "TL100", "sunset_duration")
        last = None if restored is None else MagicMock(native_value=restored)
        with (
            patch(
                "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
                new=AsyncMock(),
            ),
            patch.object(
                num, "async_get_last_number_data", new=AsyncMock(return_value=last)
            ),
        ):
            await num.async_added_to_hass()
        assert settings.sunset_minutes == (default if restored is None else 42)
