"""Tests for the sunrise/sunset/therapy buttons and their settings."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.light import ColorMode

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.button import (
    BUTTON_DESCRIPTIONS,
    BeurerButton,
)
from custom_components.beurer_daylight_lamps.number import (
    BeurerSimulationDurationNumber,
)
from custom_components.beurer_daylight_lamps.select import (
    BeurerSunriseProfileSelect,
)
from custom_components.beurer_daylight_lamps.therapy import (
    SimulationSettings,
    SunriseProfile,
    TherapyTracker,
)
from tests.conftest import create_mock_coordinator


@pytest.fixture
def instance() -> MagicMock:
    inst = MagicMock()
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst.available = True
    inst.simulation_settings = SimulationSettings()
    inst.sunrise_simulation.start_sunrise = AsyncMock()
    inst.sunrise_simulation.start_sunset = AsyncMock()
    inst.sunrise_simulation.stop = AsyncMock()
    inst.start_therapy_session = AsyncMock()
    return inst


def _button(instance, key: str) -> BeurerButton:
    desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == key)
    return BeurerButton(create_mock_coordinator(instance), "Lamp", desc)


async def test_sunrise_button_uses_settings(instance) -> None:
    """The sunrise button starts with the chosen profile and duration."""
    instance.simulation_settings.sunrise_profile = "energize"
    instance.simulation_settings.sunrise_minutes = 20
    await _button(instance, "start_sunrise").async_press()
    instance.sunrise_simulation.start_sunrise.assert_awaited_once_with(
        20, SunriseProfile.ENERGIZE
    )


async def test_sunset_stop_and_therapy_buttons(instance) -> None:
    """Sunset, stop and therapy buttons call the lamp."""
    instance.simulation_settings.sunset_minutes = 45
    await _button(instance, "start_sunset").async_press()
    instance.sunrise_simulation.start_sunset.assert_awaited_once_with(45, 0)

    await _button(instance, "stop_simulation").async_press()
    instance.sunrise_simulation.stop.assert_awaited_once()
    instance.stop_therapy_session.assert_called_once()

    await _button(instance, "start_therapy").async_press()
    instance.start_therapy_session.assert_awaited_once()


async def test_settings_entities(instance) -> None:
    """Select and numbers read and write the simulation settings."""
    coordinator = create_mock_coordinator(instance)
    select = BeurerSunriseProfileSelect(coordinator, "Lamp")
    select.async_write_ha_state = MagicMock()
    assert select.options == ["gentle", "natural", "energize", "therapy"]
    assert select.current_option == "natural"
    await select.async_select_option("gentle")
    assert instance.simulation_settings.sunrise_profile == "gentle"

    sunset = BeurerSimulationDurationNumber(coordinator, "Lamp", "sunset_duration")
    sunset.async_write_ha_state = MagicMock()
    assert sunset.native_value == 30
    await sunset.async_set_native_value(12)
    assert instance.simulation_settings.sunset_minutes == 12
    assert sunset.unique_id == "aa:bb:cc:dd:ee:ff_sunset_duration"


def _therapy_instance(today: float, goal: int = 30) -> BeurerInstance:
    inst = BeurerInstance.__new__(BeurerInstance)
    inst._mac = "AA:BB:CC:DD:EE:FF"
    inst._therapy_tracker = TherapyTracker(daily_goal_minutes=goal)
    inst._therapy_session_task = None
    inst._event_listeners = []
    inst.set_white = AsyncMock()
    inst.turn_off = AsyncMock()
    inst._safe_create_task = MagicMock()
    return inst


@pytest.mark.parametrize(("today", "expected"), [(10.0, 20.0), (35.0, 30.0)])
async def test_therapy_session_length(today, expected, monkeypatch) -> None:
    """The session lasts until the goal, or one full goal once reached."""
    inst = _therapy_instance(today)
    monkeypatch.setattr(TherapyTracker, "today_minutes", property(lambda _: today))
    inst._run_therapy_session = MagicMock(return_value="coro")

    await inst.start_therapy_session()

    inst.set_white.assert_awaited_once_with(255)
    inst._run_therapy_session.assert_called_once_with(expected * 60)


async def _run(inst: BeurerInstance, seconds: float, monkeypatch) -> None:
    async def no_sleep(_):
        return None

    monkeypatch.setattr(
        "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.asyncio.sleep",
        no_sleep,
    )
    await inst._run_therapy_session(seconds)


async def test_therapy_session_turns_off_at_end(monkeypatch) -> None:
    """At the end the lamp turns off and the event fires."""
    inst = _therapy_instance(0)
    events = []
    inst.add_event_listener(lambda t, _d: events.append(t))
    monkeypatch.setattr(BeurerInstance, "is_on", property(lambda _: True))
    monkeypatch.setattr(
        BeurerInstance, "color_mode", property(lambda _: ColorMode.WHITE)
    )
    monkeypatch.setattr(BeurerInstance, "white_brightness", property(lambda _: 255))

    await _run(inst, 0.01, monkeypatch)

    inst.turn_off.assert_awaited_once()
    assert events == ["therapy_session_finished"]


async def test_therapy_session_ends_on_change(monkeypatch) -> None:
    """Switching to color ends the session without turning off."""
    inst = _therapy_instance(0)
    monkeypatch.setattr(BeurerInstance, "is_on", property(lambda _: True))
    monkeypatch.setattr(BeurerInstance, "color_mode", property(lambda _: ColorMode.RGB))
    monkeypatch.setattr(BeurerInstance, "white_brightness", property(lambda _: 255))

    await _run(inst, 60, monkeypatch)

    inst.turn_off.assert_not_awaited()
