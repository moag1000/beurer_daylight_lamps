"""Integration conditions for Beurer Daylight Lamps (HA 2026.9+)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_ON
from homeassistant.helpers.condition import Condition, make_entity_state_condition

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CONDITIONS: dict[str, type[Condition]] = {
    # "Daily goal reached" binary sensor
    "is_therapy_goal_reached": make_entity_state_condition("binary_sensor", STATE_ON),
    # "Connected" binary sensor
    "is_connected": make_entity_state_condition("binary_sensor", STATE_ON),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the Beurer conditions."""
    return CONDITIONS
