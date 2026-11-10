"""Tests for the weak-connection repair issue and the simulation progress sensor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.beurer_daylight_lamps import beurer_daylight_lamps as bdl
from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    DOMAIN,
    FREQUENT_RECONNECT_THRESHOLD,
    FREQUENT_RECONNECT_WINDOW,
    WEAK_SIGNAL_DURATION,
)
from custom_components.beurer_daylight_lamps.sensor import (
    SIMULATION_PROGRESS_DESCRIPTION,
    BeurerSimulationProgressSensor,
)
from custom_components.beurer_daylight_lamps.signal_health import (
    PROBLEM_FREQUENT_RECONNECTS,
    PROBLEM_WEAK_SIGNAL,
    SignalHealthMonitor,
)
from custom_components.beurer_daylight_lamps.therapy import (
    SunriseProfile,
    SunriseSimulation,
)
from tests.conftest import create_mock_coordinator

ISSUE_ID = "weak_connection_aabbccddeeff"


# --- SignalHealthMonitor -----------------------------------------------------


def test_short_weak_spell_is_no_problem() -> None:
    """A weak signal shorter than the duration raises nothing."""
    mon = SignalHealthMonitor()
    mon.record_rssi(-90, 0)
    mon.record_rssi(-90, WEAK_SIGNAL_DURATION - 1)
    assert mon.problem(WEAK_SIGNAL_DURATION - 1) is None


def test_lasting_weak_signal_and_recovery() -> None:
    """A lasting weak signal is a problem until it clearly recovers."""
    mon = SignalHealthMonitor()
    mon.record_rssi(-90, 0)
    mon.record_rssi(-88, WEAK_SIGNAL_DURATION)
    assert mon.problem(WEAK_SIGNAL_DURATION) == PROBLEM_WEAK_SIGNAL
    # Between the thresholds: still a problem (no flapping)
    mon.record_rssi(-82, WEAK_SIGNAL_DURATION + 1)
    assert mon.problem(WEAK_SIGNAL_DURATION + 1) == PROBLEM_WEAK_SIGNAL
    mon.record_rssi(-70, WEAK_SIGNAL_DURATION + 2)
    assert mon.problem(WEAK_SIGNAL_DURATION + 2) is None


def test_good_reading_resets_weak_timer() -> None:
    """A reading between the thresholds restarts the weak timer."""
    mon = SignalHealthMonitor()
    mon.record_rssi(-90, 0)
    mon.record_rssi(-82, 300)
    mon.record_rssi(-90, 400)
    mon.record_rssi(-90, WEAK_SIGNAL_DURATION + 100)
    assert mon.problem(WEAK_SIGNAL_DURATION + 100) is None


def test_frequent_reconnects_and_window_expiry() -> None:
    """Many reconnects within the window are a problem until they age out."""
    mon = SignalHealthMonitor()
    for i in range(FREQUENT_RECONNECT_THRESHOLD - 1):
        mon.record_reconnect(i * 60)
    assert mon.problem(600) is None
    mon.record_reconnect(600)
    assert mon.problem(600) == PROBLEM_FREQUENT_RECONNECTS
    assert mon.reconnects_in_window(600) == FREQUENT_RECONNECT_THRESHOLD
    assert mon.problem(FREQUENT_RECONNECT_WINDOW + 61) is None


# --- Repair issue on the instance ---------------------------------------------


def _instance(hass: HomeAssistant | None) -> BeurerInstance:
    inst = BeurerInstance.__new__(BeurerInstance)
    inst._hass = hass
    inst._mac = "AA:BB:CC:DD:EE:FF"
    inst._rssi = None
    inst._signal_health = SignalHealthMonitor()
    inst._signal_issue_problem = None
    return inst


async def test_weak_signal_issue_created_and_cleared(
    hass: HomeAssistant, monkeypatch
) -> None:
    """A lasting weak RSSI raises the issue, a strong one removes it."""
    clock = [1000.0]
    monkeypatch.setattr(bdl.time, "time", lambda: clock[0])
    inst = _instance(hass)
    registry = ir.async_get(hass)

    inst.update_rssi(-92)
    assert registry.async_get_issue(DOMAIN, ISSUE_ID) is None

    clock[0] += WEAK_SIGNAL_DURATION
    inst.update_rssi(-92)
    issue = registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "weak_signal"
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["rssi"] == "-92"
    # Without a device registry entry the MAC is the name
    assert issue.translation_placeholders["name"] == "AA:BB:CC:DD:EE:FF"

    clock[0] += 10
    inst.update_rssi(-65)
    assert registry.async_get_issue(DOMAIN, ISSUE_ID) is None
    assert inst.rssi == -65


async def test_frequent_reconnect_issue_and_shutdown_clears(
    hass: HomeAssistant, monkeypatch
) -> None:
    """Frequent reconnects raise the issue; unloading removes it."""
    clock = [5000.0]
    monkeypatch.setattr(bdl.time, "time", lambda: clock[0])
    inst = _instance(hass)
    for _ in range(FREQUENT_RECONNECT_THRESHOLD):
        clock[0] += 60
        inst._signal_health.record_reconnect(clock[0])
    inst._update_signal_issue()
    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "frequent_reconnects"
    assert issue.translation_placeholders["reconnects"] == str(
        FREQUENT_RECONNECT_THRESHOLD
    )

    inst.stop_therapy_session = MagicMock()
    inst.disconnect = AsyncMock()
    await inst.shutdown()
    assert registry.async_get_issue(DOMAIN, ISSUE_ID) is None


def test_update_rssi_without_hass_and_none() -> None:
    """No hass (standalone) and None readings are harmless."""
    inst = _instance(None)
    inst.update_rssi(None)
    inst.update_rssi(-95)
    assert inst.rssi == -95


# --- Simulation progress sensor -------------------------------------------------


def test_progress_sensor_idle_and_running() -> None:
    """The sensor shows 0 % and 'none' when idle, else progress and kind."""
    inst = MagicMock()
    inst.mac = "AA:BB:CC:DD:EE:FF"
    sim = SunriseSimulation(inst)
    inst.sunrise_simulation = sim
    sensor = BeurerSimulationProgressSensor(
        create_mock_coordinator(inst), "Lamp", SIMULATION_PROGRESS_DESCRIPTION
    )
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_simulation_progress"
    assert sensor.native_value == 0
    assert sensor.extra_state_attributes == {"simulation": "none"}

    sim._running = True
    sim._kind = "sunset"
    sim._total_steps = 4
    sim._set_step(1)
    assert sensor.native_value == 25
    assert sensor.extra_state_attributes == {"simulation": "sunset"}
    inst.notify_state_changed.assert_called()


async def test_simulation_notifies_on_start_and_stop() -> None:
    """Starting and stopping a simulation pushes state to entities."""
    inst = MagicMock()
    inst.mac = "AA:BB:CC:DD:EE:FF"
    inst.is_connected = True
    inst.set_color_with_brightness_fast = AsyncMock()
    sim = SunriseSimulation(inst)

    await sim.start_sunrise(5, SunriseProfile.GENTLE)
    assert sim.kind == "sunrise"
    await asyncio.sleep(0)
    assert inst.notify_state_changed.call_count >= 2  # start + first step

    await sim.stop()
    assert sim.kind is None
    assert sim.progress_pct == 0


def test_notify_state_changed_calls_callbacks() -> None:
    """notify_state_changed runs every registered update callback."""
    inst = BeurerInstance.__new__(BeurerInstance)
    inst._update_callbacks = []
    cb = MagicMock()
    inst.set_update_callback(cb)
    inst.notify_state_changed()
    cb.assert_called_once()
