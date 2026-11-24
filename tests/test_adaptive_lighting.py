"""The Adaptive Lighting switch hands the lamp to Adaptive Lighting or keeps it.

Runs against a real BeurerInstance fed with BLE notifications and a stand-in
for ``adaptive_lighting.set_manual_control`` with its data layout.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import probatio as vol
import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beurer_daylight_lamps import switch as switch_platform
from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import DOMAIN, RESP_STATUS
from tests.tl_frames import RGB_STATUS_PLEN, WHITE_STATUS_PLEN, as_tl_frame

MAC = "AA:BB:CC:DD:EE:FF"


def _status(version: int, on: bool = True) -> bytearray:
    data = bytearray(17)
    data[6] = RGB_STATUS_PLEN if version == 2 else WHITE_STATUS_PLEN
    data[7] = RESP_STATUS
    data[8] = version
    data[9] = 1 if on else 0
    data[10] = 100
    return as_tl_frame(data)


@pytest.fixture
def al_calls(hass: HomeAssistant) -> list[dict]:
    """Stand-in for adaptive_lighting.set_manual_control, recording calls."""
    calls: list[dict] = []

    async def record(call: ServiceCall) -> None:
        calls.append(dict(call.data))

    hass.services.async_register(
        "adaptive_lighting",
        "set_manual_control",
        record,
        schema=vol.Schema(
            {
                vol.Required("lights"): cv.entity_ids,
                vol.Required("manual_control"): cv.boolean,
            }
        ),
    )
    return calls


@pytest.fixture
async def al_switch(hass: HomeAssistant, al_calls: list[dict]):
    """A lamp with its Adaptive Lighting switch, as set up by the platform."""
    MockConfigEntry(domain="adaptive_lighting").add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={"mac": MAC, "name": "Lamp"})
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "light", DOMAIN, MAC.lower(), config_entry=entry, suggested_object_id="lamp"
    )

    device = MagicMock()
    device.address = MAC
    device.name = "TL100"
    instance = BeurerInstance(device)
    instance._available = True
    coordinator = MagicMock()
    coordinator.instance = instance
    entry.runtime_data = MagicMock(coordinator=coordinator, instance=instance)

    added: list = []
    await switch_platform.async_setup_entry(hass, entry, added.extend)
    entity = next(
        e for e in added if isinstance(e, switch_platform.BeurerAdaptiveLightingSwitch)
    )
    entity.hass = hass
    entity.entity_id = "switch.lamp_adaptive_lighting"
    entity.async_write_ha_state = MagicMock()
    # Push lamp state changes to the switch, as the coordinator does
    instance.set_update_callback(entity._handle_coordinator_update)
    await entity.async_added_to_hass()
    return entity, instance


async def test_therapy_session_takes_lamp_from_adaptive_lighting(
    hass: HomeAssistant, al_switch, al_calls: list[dict]
) -> None:
    """Daylight therapy keeps Adaptive Lighting off the lamp until it ends."""
    _switch, instance = al_switch
    assert al_calls == []  # nothing to block at startup

    await instance._handle_notification(MagicMock(), _status(1))  # full white
    await hass.async_block_till_done()
    assert al_calls == [{"lights": ["light.lamp"], "manual_control": True}]

    await instance._handle_notification(MagicMock(), _status(255))  # off
    await hass.async_block_till_done()
    assert al_calls[-1] == {"lights": ["light.lamp"], "manual_control": False}
    assert len(al_calls) == 2


async def test_switch_off_blocks_adaptive_lighting(
    hass: HomeAssistant, al_switch, al_calls: list[dict]
) -> None:
    """Turning the switch off keeps Adaptive Lighting away; on hands it back."""
    switch, _instance = al_switch
    await switch.async_turn_off()
    assert al_calls == [{"lights": ["light.lamp"], "manual_control": True}]
    await switch.async_turn_on()
    assert al_calls[-1] == {"lights": ["light.lamp"], "manual_control": False}


async def test_no_switch_without_adaptive_lighting(hass: HomeAssistant) -> None:
    """Without Adaptive Lighting the switch is not created, an old one is removed."""
    entry = MockConfigEntry(domain=DOMAIN, data={"mac": MAC, "name": "Lamp"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "switch", DOMAIN, f"{MAC.lower()}_adaptive_lighting", config_entry=entry
    )
    entry.runtime_data = MagicMock()
    entry.runtime_data.instance.is_wl = False
    entry.runtime_data.instance.is_wl75 = False
    entry.runtime_data.coordinator.instance.mac = MAC

    added: list = []
    await switch_platform.async_setup_entry(hass, entry, added.extend)

    assert not any(
        isinstance(e, switch_platform.BeurerAdaptiveLightingSwitch) for e in added
    )
    assert registry.async_get(old.entity_id) is None


async def test_users_manual_control_is_kept(
    hass: HomeAssistant, al_switch, al_calls: list[dict]
) -> None:
    """If Adaptive Lighting already had the lamp on manual, it stays so after."""
    _switch, instance = al_switch
    al_entity = er.async_get(hass).async_get_or_create(
        "switch", "adaptive_lighting", "living_room", suggested_object_id="al"
    )
    hass.states.async_set(al_entity.entity_id, "on", {"manual_control": ["light.lamp"]})

    await instance._handle_notification(MagicMock(), _status(1))
    await hass.async_block_till_done()
    await instance._handle_notification(MagicMock(), _status(255))
    await hass.async_block_till_done()

    assert al_calls == [{"lights": ["light.lamp"], "manual_control": True}]
