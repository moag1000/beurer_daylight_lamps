"""Check that the shipped blueprints load and validate in Home Assistant."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from homeassistant.setup import async_setup_component

from custom_components.beurer_daylight_lamps.const import DOMAIN

BLUEPRINT_DIR = (
    Path(__file__).parent.parent / "blueprints" / "automation" / "beurer_daylight_lamps"
)

INPUTS = {
    "morning_light_therapy.yaml": [
        {"beurer_light": "light.bedroom"},
        {
            "beurer_light": "light.bedroom",
            "goal_sensor": "binary_sensor.bedroom_daily_goal_reached",
        },
    ],
    "evening_wind_down.yaml": [{"beurer_light": "light.bedroom"}],
    "focus_work_session.yaml": [{"beurer_light": "light.bedroom"}],
}


def test_every_blueprint_is_covered() -> None:
    """New blueprints need an entry in INPUTS."""
    assert {p.name for p in BLUEPRINT_DIR.glob("*.yaml")} == set(INPUTS)


def _install(config_dir: Path, blueprint: str) -> None:
    target = config_dir / "blueprints" / "automation" / DOMAIN
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(BLUEPRINT_DIR / blueprint, target / blueprint)


# Time/sun triggers keep their timers until HA stops
@pytest.mark.parametrize("expected_lingering_timers", [True])
@pytest.mark.parametrize(
    ("blueprint", "inputs"),
    [(name, inp) for name, variants in INPUTS.items() for inp in variants],
)
async def test_blueprint_validates(hass, blueprint: str, inputs: dict) -> None:
    """The blueprint creates a valid automation with the given inputs."""
    await hass.async_add_executor_job(_install, Path(hass.config.config_dir), blueprint)

    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "bp_test",
                "alias": "bp test",
                "use_blueprint": {
                    "path": f"{DOMAIN}/{blueprint}",
                    "input": inputs,
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("automation.bp_test")
    assert state is not None
    assert state.state == "on", state.attributes
