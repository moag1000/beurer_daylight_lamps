"""Tests for device triggers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beurer_daylight_lamps import device_trigger
from custom_components.beurer_daylight_lamps.const import DOMAIN


@pytest.fixture
def device_id(hass: HomeAssistant) -> str:
    """Register a lamp device with light and binary sensor entities."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")},
    )
    ent_reg = er.async_get(hass)
    for domain, unique_id, object_id in (
        ("light", "light", "lamp"),
        ("binary_sensor", "goal", "lamp_therapy_goal_reached"),
        ("binary_sensor", "conn", "lamp_connected"),
        ("binary_sensor", "other", "lamp_something_else"),
        ("sensor", "rssi", "lamp_rssi"),
    ):
        ent_reg.async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            suggested_object_id=object_id,
            device_id=device.id,
            config_entry=entry,
        )
    # An entity of another integration on the same device is ignored
    ent_reg.async_get_or_create("light", "other", "x", device_id=device.id)
    return device.id


async def test_get_triggers(hass: HomeAssistant, device_id: str) -> None:
    """Light, goal and connection entities provide triggers."""
    triggers = await device_trigger.async_get_triggers(hass, device_id)
    found = {(t["entity_id"], t["type"]) for t in triggers}
    assert found == {
        ("light.lamp", "turned_on"),
        ("light.lamp", "turned_off"),
        ("binary_sensor.lamp_therapy_goal_reached", "therapy_goal_reached"),
        ("binary_sensor.lamp_connected", "connection_lost"),
        ("binary_sensor.lamp_connected", "connection_restored"),
    }
    assert all(t["domain"] == DOMAIN for t in triggers)


async def test_trigger_capabilities(hass: HomeAssistant) -> None:
    """No extra fields."""
    caps = await device_trigger.async_get_trigger_capabilities(hass, {})
    assert caps["extra_fields"]({}) == {}


@pytest.mark.parametrize(
    ("trigger_type", "entity_id", "start", "end"),
    [
        ("turned_on", "light.lamp", STATE_OFF, STATE_ON),
        ("turned_off", "light.lamp", STATE_ON, STATE_OFF),
        (
            "therapy_goal_reached",
            "binary_sensor.lamp_therapy_goal_reached",
            STATE_OFF,
            STATE_ON,
        ),
        ("connection_lost", "binary_sensor.lamp_connected", STATE_ON, STATE_OFF),
        ("connection_restored", "binary_sensor.lamp_connected", STATE_OFF, STATE_ON),
    ],
)
async def test_attach_trigger_fires(
    hass: HomeAssistant, trigger_type: str, entity_id: str, start: str, end: str
) -> None:
    """Each trigger fires on its state change and not on the reverse one."""
    hass.states.async_set(entity_id, start)
    await hass.async_block_till_done()
    calls: list[dict] = []

    @callback
    def action(run_variables: dict, context=None) -> None:
        calls.append(run_variables)

    config = device_trigger.TRIGGER_SCHEMA(
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": "abc",
            "entity_id": entity_id,
            "type": trigger_type,
        }
    )
    unsub = await device_trigger.async_attach_trigger(
        hass, config, action, {"trigger_data": {}, "variables": {}}
    )
    hass.states.async_set(entity_id, end)
    await hass.async_block_till_done()
    assert len(calls) == 1
    hass.states.async_set(entity_id, start)
    await hass.async_block_till_done()
    assert len(calls) == 1
    unsub()


async def test_attach_unknown_type(hass: HomeAssistant) -> None:
    """An unknown type returns a no-op remover."""
    unsub = await device_trigger.async_attach_trigger(
        hass, {"type": "bogus", "entity_id": "light.lamp"}, MagicMock(), MagicMock()
    )
    assert unsub() is None


async def test_trigger_in_automation(hass: HomeAssistant, device_id: str) -> None:
    """A listed trigger passes HA validation and fires inside an automation."""
    from homeassistant.setup import async_setup_component

    triggers = await device_trigger.async_get_triggers(hass, device_id)
    trigger = next(t for t in triggers if t["type"] == "turned_on")
    hass.states.async_set("light.lamp", STATE_OFF)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": trigger,
                "action": {"event": "beurer_test_fired"},
            }
        },
    )
    fired: list = []
    hass.bus.async_listen("beurer_test_fired", fired.append)
    hass.states.async_set("light.lamp", STATE_ON)
    await hass.async_block_till_done()
    assert len(fired) == 1
