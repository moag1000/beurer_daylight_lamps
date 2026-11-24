"""Service calls through Home Assistant's real target handling (issue #18).

These tests patch nothing between ``hass.services.async_call`` and the
service handler: the registered schema validates the call, the target is
resolved through the entity, device and area registries, and the handler
reaches the lamp's instance through the config entry's runtime data.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import probatio as vol
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.beurer_daylight_lamps as integ
from custom_components.beurer_daylight_lamps.const import DOMAIN

MAC = "AA:BB:CC:DD:EE:FF"
LIGHT = "light.bedroom_lamp"

# Every entity service with minimal valid data and the instance call it makes.
# Calls get a copy: Home Assistant merges the target into the data dict.
ENTITY_SERVICES = [
    (integ.SERVICE_APPLY_PRESET, {"preset": "relax"}, "set_color_with_brightness"),
    (integ.SERVICE_SEND_RAW, {"command": "33 01 1E"}, "_send_packet"),
    (integ.SERVICE_SET_TIMER, {"minutes": 1}, "set_timer"),
    (integ.SERVICE_START_SUNRISE, {}, "sunrise_simulation.start_sunrise"),
    (integ.SERVICE_START_SUNSET, {}, "sunrise_simulation.start_sunset"),
    (integ.SERVICE_STOP_SIMULATION, {}, "sunrise_simulation.stop"),
    (integ.SERVICE_SET_ALARM, {"slot": 0, "enabled": True}, "wl90.sync_alarm"),
    (integ.SERVICE_SYNC_TIME, {}, "sync_time"),
]


def _method(instance: MagicMock, path: str) -> AsyncMock:
    target = instance
    for part in path.split("."):
        target = getattr(target, part)
    return target


@pytest.fixture
async def lamp(hass: HomeAssistant) -> MagicMock:
    """Register a lamp (config entry, device, light entity, area) and services."""
    entry = MockConfigEntry(domain=DOMAIN, data={"mac": MAC}, unique_id=MAC.lower())
    entry.add_to_hass(hass)

    area = ar.async_get(hass).async_create("Bedroom")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, MAC)},
    )
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    er.async_get(hass).async_get_or_create(
        "light",
        DOMAIN,
        MAC.lower(),
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="bedroom_lamp",
    )

    instance = MagicMock()
    instance.mac = MAC
    instance.is_wl = True
    instance.is_wl75 = False
    for _, _, path in ENTITY_SERVICES:
        parent, _, name = path.rpartition(".")
        owner = _method(instance, parent) if parent else instance
        setattr(owner, name, AsyncMock(return_value=True))
    entry.runtime_data = MagicMock(instance=instance)

    await integ._async_setup_services(hass)
    instance.device_id = device.id
    instance.area_id = area.id
    return instance


@pytest.mark.parametrize("case", ENTITY_SERVICES, ids=lambda case: case[0])
@pytest.mark.parametrize("target_kind", ["entity_id", "device_id", "area_id"])
async def test_service_reaches_lamp_through_target(
    hass: HomeAssistant,
    lamp: MagicMock,
    case: tuple[str, dict, str],
    target_kind: str,
) -> None:
    """Each service accepts an entity, device or area target (README example)."""
    service, data, method = case
    target = {
        "entity_id": LIGHT,
        "device_id": lamp.device_id,
        "area_id": lamp.area_id,
    }[target_kind]
    await hass.services.async_call(
        DOMAIN, service, dict(data), target={target_kind: target}, blocking=True
    )
    _method(lamp, method).assert_awaited_once()


@pytest.mark.parametrize(("service", "data", "method"), ENTITY_SERVICES)
async def test_service_without_target_is_rejected(
    hass: HomeAssistant, lamp: MagicMock, service: str, data: dict, method: str
) -> None:
    """A call without any target fails validation instead of doing nothing."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, service, dict(data), blocking=True)
    _method(lamp, method).assert_not_awaited()


async def test_readme_set_timer_example(hass: HomeAssistant, lamp: MagicMock) -> None:
    """The exact call from issue #18 / the README works."""
    await hass.services.async_call(
        DOMAIN,
        integ.SERVICE_SET_TIMER,
        {"minutes": 1},
        target={"entity_id": LIGHT},
        blocking=True,
    )
    lamp.set_timer.assert_awaited_once_with(1)
