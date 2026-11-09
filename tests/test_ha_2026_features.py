"""Tests for event, time, trigger, condition and LLM platforms."""

from __future__ import annotations

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.llm import LLM_API_ASSIST, LLMContext, ToolInput

from custom_components.beurer_daylight_lamps import condition, llm, trigger
from custom_components.beurer_daylight_lamps import time as time_platform
from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    DOMAIN,
    EVENT_TYPE_SUNRISE_FINISHED,
    EVENT_TYPE_TIMER_FINISHED,
    LAMP_EVENT_TYPES,
)
from custom_components.beurer_daylight_lamps.event import BeurerLampEvent
from custom_components.beurer_daylight_lamps.wl90 import AlarmItem
from tests.conftest import create_mock_coordinator

MAC = "AA:BB:CC:DD:EE:FF"


# =============================================================================
# Lamp event listeners on BeurerInstance
# =============================================================================


def _bare_instance() -> BeurerInstance:
    """Create a BeurerInstance without running its constructor."""
    instance = BeurerInstance.__new__(BeurerInstance)
    instance._event_listeners = []
    instance._mac = MAC
    return instance


def test_emit_lamp_event_calls_listeners() -> None:
    """Listeners get the event type and data; removal stops delivery."""
    instance = _bare_instance()
    received: list[tuple[str, dict]] = []
    remove = instance.add_event_listener(lambda t, d: received.append((t, d)))

    instance.emit_lamp_event(EVENT_TYPE_TIMER_FINISHED, {"timer": "light"})
    remove()
    instance.emit_lamp_event(EVENT_TYPE_TIMER_FINISHED)
    remove()  # removing twice is harmless

    assert received == [(EVENT_TYPE_TIMER_FINISHED, {"timer": "light"})]


def test_emit_lamp_event_survives_broken_listener() -> None:
    """A failing listener does not stop the others."""
    instance = _bare_instance()
    received: list[str] = []

    def broken(event_type: str, data: dict) -> None:
        raise RuntimeError("boom")

    instance.add_event_listener(broken)
    instance.add_event_listener(lambda t, _d: received.append(t))
    instance.emit_lamp_event(EVENT_TYPE_SUNRISE_FINISHED)

    assert received == [EVENT_TYPE_SUNRISE_FINISHED]


# =============================================================================
# Event entity
# =============================================================================


def test_event_entity_setup() -> None:
    """The event entity offers all lamp event types."""
    instance = MagicMock()
    instance.mac = MAC
    entity = BeurerLampEvent(instance, "Test WL90")

    assert entity.unique_id == "aa:bb:cc:dd:ee:ff_lamp_event"
    assert entity.event_types == LAMP_EVENT_TYPES
    assert entity.translation_key == "lamp_event"
    assert entity.device_info["identifiers"] == {(DOMAIN, "aa:bb:cc:dd:ee:ff")}


async def test_event_entity_records_events() -> None:
    """A lamp event is recorded on the entity and written to the state."""
    instance = _bare_instance()
    entity = BeurerLampEvent(instance, "Test WL90")
    entity.async_on_remove = MagicMock()
    entity.async_write_ha_state = MagicMock()

    with patch(
        "homeassistant.components.event.EventEntity.async_added_to_hass",
        AsyncMock(),
    ):
        await entity.async_added_to_hass()

    instance.emit_lamp_event(EVENT_TYPE_TIMER_FINISHED, {"timer": "light"})

    entity.async_write_ha_state.assert_called_once()
    assert entity.state_attributes == {
        "event_type": EVENT_TYPE_TIMER_FINISHED,
        "timer": "light",
    }
    entity.async_on_remove.assert_called_once()


# =============================================================================
# Time entities
# =============================================================================


def _wl_instance() -> MagicMock:
    instance = MagicMock()
    instance.mac = MAC
    instance.available = True
    instance.is_wl = True
    instance.wl90 = MagicMock()
    instance.wl90.alarms = [AlarmItem(slot=i) for i in range(3)]
    instance.wl90.sync_alarm = AsyncMock(return_value=True)
    return instance


async def test_time_setup_only_for_wake_up_lights() -> None:
    """Alarm time entities exist only on WL lamps, one per slot."""
    instance = _wl_instance()
    entry = SimpleNamespace(
        data={"name": "Test WL90"},
        runtime_data=SimpleNamespace(
            instance=instance, coordinator=create_mock_coordinator(instance)
        ),
    )
    add = MagicMock()
    await time_platform.async_setup_entry(MagicMock(), entry, add)
    entities = list(add.call_args[0][0])
    assert [e.unique_id for e in entities] == [
        f"aa:bb:cc:dd:ee:ff_alarm_{n}_time" for n in (1, 2, 3)
    ]

    instance.is_wl = False
    add.reset_mock()
    await time_platform.async_setup_entry(MagicMock(), entry, add)
    add.assert_not_called()


async def test_time_value_and_set() -> None:
    """The entity shows the alarm time and writes changes to the lamp."""
    instance = _wl_instance()
    instance.wl90.alarms[1].hour = 6
    instance.wl90.alarms[1].minute = 45
    entity = time_platform.BeurerAlarmTime(
        create_mock_coordinator(instance), "Test WL90", 1
    )
    entity.async_write_ha_state = MagicMock()

    assert entity.translation_key == "alarm_2_time"
    assert entity.native_value == time(6, 45)
    assert entity.available is True

    await entity.async_set_value(time(7, 5))

    alarm = instance.wl90.alarms[1]
    assert (alarm.hour, alarm.minute) == (7, 5)
    instance.wl90.sync_alarm.assert_awaited_once_with(1, alarm)
    entity.async_write_ha_state.assert_called_once()


async def test_time_missing_slot() -> None:
    """A slot that does not exist is unavailable and ignores writes."""
    instance = _wl_instance()
    instance.wl90.alarms = []
    entity = time_platform.BeurerAlarmTime(
        create_mock_coordinator(instance), "Test WL90", 0
    )
    assert entity.available is False
    assert entity.native_value is None
    await entity.async_set_value(time(7, 0))
    instance.wl90.sync_alarm.assert_not_awaited()


# =============================================================================
# Triggers and conditions
# =============================================================================


async def test_triggers_offered(hass) -> None:
    """Every trigger in triggers.yaml has an implementation and vice versa."""
    triggers = await trigger.async_get_triggers(hass)
    assert set(triggers) == {*LAMP_EVENT_TYPES, "therapy_goal_reached"}


@pytest.mark.parametrize("event_type", LAMP_EVENT_TYPES)
def test_lamp_event_trigger_matches_only_its_type(event_type: str) -> None:
    """A lamp event trigger fires only for its own event type."""
    trigger_cls = trigger.TRIGGERS[event_type]
    trigger_obj = trigger_cls.__new__(trigger_cls)
    report = MagicMock()
    for other in LAMP_EVENT_TYPES:
        state = SimpleNamespace(attributes={"event_type": other})
        assert trigger_obj.is_valid_state(state, report) is (other == event_type)


async def test_timer_finished_trigger_in_automation(hass) -> None:
    """The integration trigger works in a real automation."""
    from homeassistant.setup import async_setup_component

    entity_id = "event.bedroom_lamp_event"
    hass.states.async_set(entity_id, "unknown", {"event_type": None})
    calls: list = []
    hass.services.async_register("test", "automation", calls.append)
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": {
                    "trigger": f"{DOMAIN}.timer_finished",
                    "target": {"entity_id": entity_id},
                },
                "actions": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id, "2026-11-09T20:00:00.000+00:00", {"event_type": "timer_cancelled"}
    )
    await hass.async_block_till_done()
    assert calls == []

    hass.states.async_set(
        entity_id, "2026-11-09T20:05:00.000+00:00", {"event_type": "timer_finished"}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_conditions_offered(hass) -> None:
    """Conditions are offered under the keys used in conditions.yaml."""
    conditions = await condition.async_get_conditions(hass)
    assert set(conditions) == {"is_therapy_goal_reached", "is_connected"}


# =============================================================================
# LLM tools
# =============================================================================


def _llm_context() -> LLMContext:
    return LLMContext(
        platform="conversation",
        context=None,
        language="en",
        assistant="conversation",
        device_id=None,
    )


def _llm_setup(hass, *, exposed: bool = True):
    """Patch one loaded lamp with an exposed light entity."""
    instance = MagicMock()
    instance.mac = MAC
    instance.therapy_tracker = SimpleNamespace(
        today_minutes=12.34,
        week_minutes=80.0,
        daily_goal_minutes=30,
        goal_reached=False,
        goal_progress_pct=41,
    )
    instance.sunrise_simulation.is_running = True
    entry = SimpleNamespace(
        title="Bedroom", runtime_data=SimpleNamespace(instance=instance)
    )
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = "light.bedroom_lamp"
    return [
        patch.object(hass.config_entries, "async_loaded_entries", return_value=[entry]),
        patch.object(llm.er, "async_get", return_value=ent_reg),
        patch.object(llm, "async_should_expose", return_value=exposed),
    ]


def _enter(patches):
    for p in patches:
        p.start()


async def test_llm_tools_only_with_exposed_lamps(hass) -> None:
    """Tools are offered for Assist only when a lamp is exposed."""
    patches = _llm_setup(hass, exposed=False)
    _enter(patches)
    try:
        assert llm.async_get_tools(hass, _llm_context(), LLM_API_ASSIST) is None
    finally:
        patch.stopall()

    _enter(_llm_setup(hass))
    try:
        tools = llm.async_get_tools(hass, _llm_context(), LLM_API_ASSIST)
        assert tools is not None
        names = [t.name for t in tools.tools]
        assert all(n.startswith(f"{DOMAIN}__") for n in names)
        assert all(t.integration == DOMAIN for t in tools.tools)
        assert llm.async_get_tools(hass, _llm_context(), "other_api") is None
    finally:
        patch.stopall()


async def test_llm_start_sunrise_calls_service(hass) -> None:
    """The sunrise tool calls the service on the matching lamp."""
    calls = []

    async def record(call):
        calls.append(call)

    hass.services.async_register(DOMAIN, "start_sunrise", record)
    _enter(_llm_setup(hass))
    try:
        tool = llm.StartSunriseTool()
        args = tool.parameters({"lamp": "bed", "duration": 20})
        result = await tool.async_call(
            hass,
            ToolInput(tool_name=tool.name, tool_args=args),
            _llm_context(),
        )
        assert result == {"success": True, "lamps": ["Bedroom"]}
        assert calls[0].data == {
            "duration": 20,
            "profile": "natural",
            "entity_id": ["light.bedroom_lamp"],
        }

        result = await tool.async_call(
            hass,
            ToolInput(tool_name=tool.name, tool_args={"lamp": "kitchen"}),
            _llm_context(),
        )
        assert result["success"] is False
        assert len(calls) == 1
    finally:
        patch.stopall()


async def test_llm_sunset_and_stop(hass) -> None:
    """Sunset and stop tools call their services."""
    calls = []

    async def record(call):
        calls.append(call)

    hass.services.async_register(DOMAIN, "start_sunset", record)
    hass.services.async_register(DOMAIN, "stop_simulation", record)
    _enter(_llm_setup(hass))
    try:
        await llm.StartSunsetTool().async_call(
            hass, ToolInput(tool_name="x", tool_args={}), _llm_context()
        )
        await llm.StopSimulationTool().async_call(
            hass, ToolInput(tool_name="x", tool_args={}), _llm_context()
        )
        assert [c.service for c in calls] == ["start_sunset", "stop_simulation"]
        assert calls[0].data["duration"] == 30
        assert calls[0].data["end_brightness"] == 0
    finally:
        patch.stopall()


async def test_llm_therapy_status(hass) -> None:
    """The status tool reports the therapy tracker values."""
    _enter(_llm_setup(hass))
    try:
        result = await llm.GetTherapyStatusTool().async_call(
            hass, ToolInput(tool_name="x", tool_args={}), _llm_context()
        )
    finally:
        patch.stopall()
    assert result == {
        "success": True,
        "lamps": [
            {
                "lamp": "Bedroom",
                "today_minutes": 12.3,
                "week_minutes": 80.0,
                "daily_goal_minutes": 30,
                "goal_reached": False,
                "goal_progress_percent": 41,
                "simulation_running": True,
            }
        ],
    }


async def test_llm_no_lamp_exposed(hass) -> None:
    """Without exposed lamps the status tool reports an error."""
    _enter(_llm_setup(hass, exposed=False))
    try:
        result = await llm.GetTherapyStatusTool().async_call(
            hass, ToolInput(tool_name="x", tool_args={}), _llm_context()
        )
    finally:
        patch.stopall()
    assert result["success"] is False
