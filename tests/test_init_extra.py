"""Extra coverage for setup helpers and services in __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.beurer_daylight_lamps as integ
from custom_components.beurer_daylight_lamps.const import DOMAIN

PKG = "custom_components.beurer_daylight_lamps"


def _instance(mac: str = "AA:BB:CC:DD:EE:FF") -> MagicMock:
    inst = MagicMock()
    inst.mac = mac
    inst._send_packet = AsyncMock(return_value=True)
    inst.set_timer = AsyncMock(return_value=True)
    inst.sync_time = AsyncMock(return_value=True)
    inst.set_color_brightness = AsyncMock()
    inst.sunrise_simulation.start_sunrise = AsyncMock()
    inst.sunrise_simulation.start_sunset = AsyncMock()
    inst.sunrise_simulation.stop = AsyncMock()
    inst.is_wl = True
    inst.is_wl75 = False
    inst.wl90.sync_alarm = AsyncMock(return_value=True)
    return inst


@pytest.fixture
async def services(hass: HomeAssistant):
    """Register the services with a patchable instance lookup."""
    with patch(
        f"{PKG}._async_get_instances_from_target", new=AsyncMock(return_value=[])
    ) as lookup:
        await integ._async_setup_services(hass)
        yield lookup


async def _call(hass: HomeAssistant, service: str, data: dict | None = None) -> None:
    await hass.services.async_call(DOMAIN, service, data or {}, blocking=True)


class TestServicesWithoutTargets:
    """Services return quietly (or raise) when nothing is targeted."""

    @pytest.mark.parametrize(
        ("service", "data"),
        [
            (integ.SERVICE_SET_TIMER, {"minutes": 10}),
            (integ.SERVICE_START_SUNRISE, {}),
            (integ.SERVICE_START_SUNSET, {}),
            (integ.SERVICE_STOP_SIMULATION, {}),
            (integ.SERVICE_SET_ALARM, {"slot": 0, "enabled": True}),
            (integ.SERVICE_SYNC_TIME, {}),
        ],
    )
    async def test_no_instances(
        self, hass: HomeAssistant, services, service: str, data: dict
    ) -> None:
        await _call(hass, service, data)

    async def test_raw_without_targets_raises(
        self, hass: HomeAssistant, services
    ) -> None:
        with pytest.raises(ServiceValidationError):
            await _call(hass, integ.SERVICE_SEND_RAW, {"command": "3E 1E"})


class TestServices:
    """Service handlers with targets."""

    async def test_preset_brightness_only(self, hass: HomeAssistant, services) -> None:
        inst = _instance()
        services.return_value = [inst]
        with patch.dict(integ.PRESETS, {"relax": {"brightness": 40}}):
            await _call(hass, integ.SERVICE_APPLY_PRESET, {"preset": "relax"})
        inst.set_color_brightness.assert_awaited_once_with(40)

    async def test_raw_invalid_hex(self, hass: HomeAssistant, services) -> None:
        services.return_value = [_instance()]
        with pytest.raises(ServiceValidationError):
            await _call(hass, integ.SERVICE_SEND_RAW, {"command": "ZZ"})

    async def test_raw_failure_lists_devices(
        self, hass: HomeAssistant, services
    ) -> None:
        ok, bad = _instance("AA:AA:AA:AA:AA:AA"), _instance("BB:BB:BB:BB:BB:BB")
        bad._send_packet.return_value = False
        services.return_value = [ok, bad]
        with pytest.raises(ServiceValidationError) as err:
            await _call(hass, integ.SERVICE_SEND_RAW, {"command": "0x3E 0x1E"})
        assert err.value.translation_placeholders == {"devices": "BB:BB:BB:BB:BB:BB"}
        ok._send_packet.assert_awaited_once_with([0x3E, 0x1E])

    async def test_timer(self, hass: HomeAssistant, services) -> None:
        ok, bad = _instance(), _instance()
        bad.set_timer.return_value = False
        services.return_value = [ok, bad]
        await _call(hass, integ.SERVICE_SET_TIMER, {"minutes": 15})
        ok.set_timer.assert_awaited_once_with(15)

    async def test_sunrise_and_stop(self, hass: HomeAssistant, services) -> None:
        inst = _instance()
        services.return_value = [inst]
        await _call(hass, integ.SERVICE_START_SUNRISE, {"duration": 20})
        assert inst.sunrise_simulation.start_sunrise.await_args.args[0] == 20
        await _call(hass, integ.SERVICE_STOP_SIMULATION)
        inst.sunrise_simulation.stop.assert_awaited_once()

    async def test_sunrise_unknown_profile(self, hass: HomeAssistant, services) -> None:
        inst = _instance()
        services.return_value = [inst]
        with patch(f"{PKG}.SunriseProfile", side_effect=ValueError):
            await _call(hass, integ.SERVICE_START_SUNRISE, {})
        inst.sunrise_simulation.start_sunrise.assert_not_awaited()

    async def test_set_alarm(self, hass: HomeAssistant, services) -> None:
        wl90, tl, wl75, failing = _instance(), _instance(), _instance(), _instance()
        tl.is_wl = False
        wl75.is_wl75 = True
        failing.wl90.sync_alarm.return_value = False
        services.return_value = [wl90, tl, wl75, failing]
        await _call(
            hass,
            integ.SERVICE_SET_ALARM,
            {
                "slot": 2,
                "enabled": True,
                "hour": 6,
                "minute": 45,
                "days": "Mon, Sat,Funday",
            },
        )
        slot, alarm = wl90.wl90.sync_alarm.await_args.args
        assert slot == 2
        assert (alarm.hour, alarm.minute) == (6, 45)
        assert alarm.days_list == ["Mon", "Sat"]
        tl.wl90.sync_alarm.assert_not_awaited()
        wl75.wl90.sync_alarm.assert_not_awaited()
        failing.wl90.sync_alarm.assert_awaited_once()

    async def test_sync_time(self, hass: HomeAssistant, services) -> None:
        ok, bad = _instance("AA:AA:AA:AA:AA:AA"), _instance("BB:BB:BB:BB:BB:BB")
        services.return_value = [ok]
        await _call(hass, integ.SERVICE_SYNC_TIME)
        ok.sync_time.assert_awaited_once()
        bad.sync_time.return_value = False
        services.return_value = [ok, bad]
        with pytest.raises(ServiceValidationError):
            await _call(hass, integ.SERVICE_SYNC_TIME)


class TestSetupHelpers:
    """Instance creation and Bluetooth callbacks."""

    def test_create_instance_failure_raises_issue(self, hass: HomeAssistant) -> None:
        entry = MockConfigEntry(
            domain=DOMAIN, data={"mac": "AA:BB:CC:DD:EE:FF", "name": "TL100"}
        )
        with (
            patch(f"{PKG}.BeurerInstance", side_effect=ValueError("boom")),
            pytest.raises(ConfigEntryNotReady),
        ):
            integ._create_instance(hass, entry, MagicMock(), -60, True)  # noqa: FBT003
        issue = ir.async_get(hass).async_get_issue(
            DOMAIN, f"initialization_failed_{entry.entry_id}"
        )
        assert issue is not None
        assert issue.translation_placeholders["error"] == "boom"

    def test_create_instance_unavailable(self, hass: HomeAssistant) -> None:
        entry = MockConfigEntry(domain=DOMAIN, data={"mac": "AA:BB:CC:DD:EE:FF"})
        with patch(f"{PKG}.BeurerInstance") as cls:
            inst = integ._create_instance(hass, entry, MagicMock(), None, False)  # noqa: FBT003
        assert inst is cls.return_value
        assert inst._ble_available is False
        assert inst._device_name == "Beurer Lamp"

    def test_bluetooth_callbacks(self, hass: HomeAssistant) -> None:
        entry = MagicMock()
        inst = MagicMock()
        new_device = object()
        with (
            patch(f"{PKG}.bluetooth.async_register_callback") as reg,
            patch(f"{PKG}.bluetooth.async_track_unavailable") as track,
            patch(f"{PKG}._get_ble_device_and_rssi", return_value=(new_device, -55)),
        ):
            integ._register_bluetooth_callbacks(hass, entry, inst, "AA:BB")
            discovered = reg.call_args.args[1]
            unavailable = track.call_args.args[1]
            info = MagicMock(rssi=-55, address="AA:BB", source="hci0")
            discovered(info, MagicMock())
            inst.update_rssi.assert_called_once_with(-55)
            inst.update_ble_device.assert_called_once_with(new_device)
            inst.mark_seen.assert_called_once()
            info.rssi = None
            discovered(info, MagicMock())
            assert inst.update_rssi.call_count == 1
            unavailable(info)
            inst.mark_unavailable.assert_called_once()
        assert entry.async_on_unload.call_count == 2


async def test_remove_config_entry_device(hass: HomeAssistant) -> None:
    assert await integ.async_remove_config_entry_device(hass, MagicMock(), MagicMock())
