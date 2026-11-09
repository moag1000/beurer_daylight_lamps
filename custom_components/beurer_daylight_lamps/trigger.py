"""Integration triggers for Beurer Daylight Lamps.

Shown as their own building blocks in the automation editor (HA 2026.9+).
The event triggers fire on the lamp's event entity (see event.py); the goal
trigger fires when the "Daily goal reached" binary sensor turns on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.const import STATE_ON
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    StatelessEntityTriggerBase,
    Trigger,
    make_entity_target_state_trigger,
)

from .const import (
    EVENT_TYPE_SLEEP_TIMER_FINISHED,
    EVENT_TYPE_SUNRISE_FINISHED,
    EVENT_TYPE_SUNSET_FINISHED,
    EVENT_TYPE_THERAPY_SESSION_FINISHED,
    EVENT_TYPE_TIMER_CANCELLED,
    EVENT_TYPE_TIMER_FINISHED,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.trigger import NotTriggeredReasonReporter

ATTR_EVENT_TYPE = "event_type"


class LampEventTrigger(StatelessEntityTriggerBase):
    """Fires when the lamp's event entity records one specific event type."""

    _domain_specs = {"event": DomainSpec()}
    _lamp_event_type: str

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check that the recorded event is the one this trigger is for."""
        return state.attributes.get(ATTR_EVENT_TYPE) == self._lamp_event_type


def _lamp_event_trigger(event_type: str) -> type[Trigger]:
    """Create a trigger class for one lamp event type."""
    return type(
        f"LampEventTrigger_{event_type}",
        (LampEventTrigger,),
        {"_lamp_event_type": event_type},
    )


TRIGGERS: dict[str, type[Trigger]] = {
    EVENT_TYPE_TIMER_FINISHED: _lamp_event_trigger(EVENT_TYPE_TIMER_FINISHED),
    EVENT_TYPE_TIMER_CANCELLED: _lamp_event_trigger(EVENT_TYPE_TIMER_CANCELLED),
    EVENT_TYPE_SLEEP_TIMER_FINISHED: _lamp_event_trigger(
        EVENT_TYPE_SLEEP_TIMER_FINISHED
    ),
    EVENT_TYPE_SUNRISE_FINISHED: _lamp_event_trigger(EVENT_TYPE_SUNRISE_FINISHED),
    EVENT_TYPE_SUNSET_FINISHED: _lamp_event_trigger(EVENT_TYPE_SUNSET_FINISHED),
    EVENT_TYPE_THERAPY_SESSION_FINISHED: _lamp_event_trigger(
        EVENT_TYPE_THERAPY_SESSION_FINISHED
    ),
    "therapy_goal_reached": make_entity_target_state_trigger("binary_sensor", STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the Beurer triggers."""
    return TRIGGERS
