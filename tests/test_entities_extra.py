"""Extra coverage for switch and sensor entities."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beurer_daylight_lamps.const import DOMAIN
from custom_components.beurer_daylight_lamps.sensor import (
    CONNECTION_HEALTH_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    THERAPY_SENSOR_DESCRIPTIONS,
    BeurerConnectionHealthSensor,
    BeurerPersonTherapySensor,
    BeurerSensor,
    BeurerTherapySensor,
    async_setup_entry as sensor_setup_entry,
)
from custom_components.beurer_daylight_lamps.switch import (
    DEVICE_SWITCH_DESCRIPTIONS,
    BeurerAlarmSwitch,
    BeurerDeviceSwitch,
)
from custom_components.beurer_daylight_lamps.wl90 import AlarmItem


def _desc(descriptions, key):
    return next(d for d in descriptions if d.key == key)


@pytest.fixture
def coordinator() -> MagicMock:
    """Return a coordinator with a fake instance."""
    coord = MagicMock()
    inst = coord.instance
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst.available = True
    inst.set_feedback = AsyncMock()
    inst.set_fade = AsyncMock()
    inst.wl90 = MagicMock()
    inst.wl90.alarms = [AlarmItem(slot=0, hour=6, minute=5), AlarmItem(slot=1)]
    inst.wl90.sync_alarm = AsyncMock(return_value=True)
    return coord


class TestDeviceSwitch:
    """Feedback sound and fade switches."""

    async def test_feedback(self, coordinator: MagicMock) -> None:
        sw = BeurerDeviceSwitch(
            coordinator, "TL100", _desc(DEVICE_SWITCH_DESCRIPTIONS, "feedback_sound")
        )
        coordinator.instance.feedback_enabled = True
        assert sw.is_on is True
        assert sw.available
        assert sw.unique_id == "aa:bb:cc:dd:ee:ff_feedback_sound"
        assert sw.device_info["manufacturer"] == "Beurer"
        await sw.async_turn_on()
        coordinator.instance.set_feedback.assert_awaited_with(True)
        await sw.async_turn_off()
        coordinator.instance.set_feedback.assert_awaited_with(False)
        coordinator.instance.set_fade.assert_not_awaited()

    async def test_fade(self, coordinator: MagicMock) -> None:
        sw = BeurerDeviceSwitch(
            coordinator, "TL100", _desc(DEVICE_SWITCH_DESCRIPTIONS, "fade")
        )
        coordinator.instance.fade_enabled = False
        assert sw.is_on is False
        await sw.async_turn_on()
        coordinator.instance.set_fade.assert_awaited_with(True)
        await sw.async_turn_off()
        coordinator.instance.set_fade.assert_awaited_with(False)

    async def test_unknown_key(self, coordinator: MagicMock) -> None:
        desc = MagicMock()
        desc.key = "other"
        sw = BeurerDeviceSwitch(coordinator, "TL100", desc)
        assert sw.is_on is None
        await sw.async_turn_on()
        await sw.async_turn_off()
        coordinator.instance.set_feedback.assert_not_awaited()
        coordinator.instance.set_fade.assert_not_awaited()


class TestAlarmSwitch:
    """Alarm slot switches."""

    async def test_toggle(self, coordinator: MagicMock) -> None:
        sw = BeurerAlarmSwitch(coordinator, "WL90", 0)
        sw.async_write_ha_state = MagicMock()
        assert sw.unique_id == "aa:bb:cc:dd:ee:ff_alarm_1"
        assert sw.available
        assert not sw.is_on
        await sw.async_turn_on()
        assert sw.is_on
        coordinator.instance.wl90.sync_alarm.assert_awaited_with(
            0, coordinator.instance.wl90.alarms[0]
        )
        await sw.async_turn_off()
        assert not sw.is_on
        assert sw.async_write_ha_state.call_count == 2
        attrs = sw.extra_state_attributes
        assert attrs["time"] == "06:05"
        assert attrs["slot"] == 0
        assert attrs["days"] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
        assert sw.device_info["name"] == "WL90"

    async def test_missing_slot(self, coordinator: MagicMock) -> None:
        sw = BeurerAlarmSwitch(coordinator, "WL75", 2)
        assert not sw.available
        assert not sw.is_on
        assert sw.extra_state_attributes == {}
        await sw.async_turn_on()
        await sw.async_turn_off()
        coordinator.instance.wl90.sync_alarm.assert_not_awaited()

    async def test_no_controller(self, coordinator: MagicMock) -> None:
        coordinator.instance.wl90 = None
        sw = BeurerAlarmSwitch(coordinator, "TL100", 0)
        assert not sw.available
        await sw.async_turn_on()


class TestSensors:
    """Diagnostic, therapy and health sensors."""

    def test_last_time_sync(self, coordinator: MagicMock) -> None:
        sensor = BeurerSensor(
            coordinator, "WL90", _desc(SENSOR_DESCRIPTIONS, "last_time_sync")
        )
        coordinator.instance.last_time_sync = 0
        assert sensor.native_value is None
        coordinator.instance.last_time_sync = 1_700_000_000
        assert isinstance(sensor.native_value, datetime)

    def test_unknown_keys(self, coordinator: MagicMock) -> None:
        desc = MagicMock()
        desc.key = "other"
        assert BeurerSensor(coordinator, "x", desc).native_value is None
        assert BeurerTherapySensor(coordinator, "x", desc).native_value is None
        health = BeurerConnectionHealthSensor(coordinator, "x", desc)
        assert health.native_value is None
        assert health.extra_state_attributes is None

    def test_therapy_device_info(self, coordinator: MagicMock) -> None:
        sensor = BeurerTherapySensor(
            coordinator, "TL100", _desc(THERAPY_SENSOR_DESCRIPTIONS, "therapy_today")
        )
        assert sensor.available
        assert sensor.device_info["name"] == "TL100"

    def test_health(self, coordinator: MagicMock) -> None:
        inst = coordinator.instance
        inst.reconnect_count = 3
        inst.command_success_rate = 97
        inst.connection_uptime_seconds = 120
        inst.total_commands = 40
        values = {}
        for desc in CONNECTION_HEALTH_SENSOR_DESCRIPTIONS:
            sensor = BeurerConnectionHealthSensor(coordinator, "TL100", desc)
            values[desc.key] = sensor.native_value
            assert sensor.available
            assert sensor.device_info["manufacturer"] == "Beurer"
        assert values == {
            "reconnect_count": 3,
            "command_success_rate": 97,
            "connection_uptime": 120,
        }
        rate = BeurerConnectionHealthSensor(
            coordinator,
            "TL100",
            _desc(CONNECTION_HEALTH_SENSOR_DESCRIPTIONS, "command_success_rate"),
        )
        assert rate.extra_state_attributes == {"total_commands": 40}


class TestPersonSensors:
    """Per-person therapy aggregation on the Therapy Hub."""

    async def test_setup_creates_person_sensors(
        self, hass: HomeAssistant, coordinator: MagicMock
    ) -> None:
        entry = MockConfigEntry(
            domain=DOMAIN, data={"name": "TL100"}, options={"therapy_goal": 20}
        )
        entry.add_to_hass(hass)
        entry.runtime_data = MagicMock(coordinator=coordinator)
        hass.states.async_set("person.anna", "home")
        added: list = []

        def add(entities, *args):
            added.extend(entities)

        await sensor_setup_entry(hass, entry, add)
        persons = [e for e in added if isinstance(e, BeurerPersonTherapySensor)]
        assert {p.unique_id for p in persons} == {
            "therapy_today_anna",
            "therapy_week_anna",
            "therapy_progress_anna",
        }

        # A person added later gets its own sensors, exactly once
        hass.states.async_set("person.ben", "home")
        await hass.async_block_till_done()
        hass.states.async_remove("person.ben")
        hass.states.async_set("person.ben", "home")
        await hass.async_block_till_done()
        ben = [e for e in added if e.unique_id and e.unique_id.endswith("_ben")]
        assert len(ben) == 3

        # A second lamp does not add the person sensors again
        before = len(added)
        await sensor_setup_entry(hass, entry, add)
        assert not any(
            isinstance(e, BeurerPersonTherapySensor) for e in added[before:]
        )

        # Values come from the hub, the goal from the first entry
        progress = next(p for p in persons if p.unique_id == "therapy_progress_anna")
        assert progress.native_unit_of_measurement == "%"
        assert progress.device_info["name"] == "Beurer Therapy Hub"
        with (
            patch(
                "custom_components.beurer_daylight_lamps.sensor.today_minutes_for",
                return_value=12.34,
            ),
            patch(
                "custom_components.beurer_daylight_lamps.sensor.week_minutes_for",
                return_value=56.78,
            ),
            patch(
                "custom_components.beurer_daylight_lamps.sensor.goal_progress_for",
                return_value=61,
            ) as goal,
        ):
            values = {p.unique_id: p.native_value for p in persons}
        assert values == {
            "therapy_today_anna": 12.3,
            "therapy_week_anna": 56.8,
            "therapy_progress_anna": 61,
        }
        assert goal.call_args.args[2] == 20

    def test_default_goal_without_entries(self, hass: HomeAssistant) -> None:
        sensor = BeurerPersonTherapySensor(hass, "person.x", "x", "week")
        assert sensor.native_unit_of_measurement == "min"
        assert sensor._first_goal() > 0
