"""LLM tools for Assist and other conversation agents (HA 2026.9+).

Lets a conversation agent start a sunrise or sunset, stop a running
simulation and read the daily light therapy status. Only lamps whose light
entity is exposed to the assistant are visible to the tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import probatio as vol
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.llm import LLM_API_ASSIST, LLMContext, Tool, ToolInput

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.util.json import JsonObjectType

    from .data import BeurerConfigEntry

TOOL_PREFIX = f"{DOMAIN}__"
ATTR_LAMP = "lamp"


def _exposed_lamps(
    hass: HomeAssistant, llm_context: LLMContext
) -> list[tuple[BeurerConfigEntry, str]]:
    """Return (config entry, light entity id) for lamps exposed to the assistant."""
    ent_reg = er.async_get(hass)
    lamps: list[tuple[BeurerConfigEntry, str]] = []
    entry: BeurerConfigEntry
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        entity_id = ent_reg.async_get_entity_id(
            Platform.LIGHT, DOMAIN, format_mac(entry.runtime_data.instance.mac)
        )
        if entity_id and async_should_expose(hass, llm_context.assistant, entity_id):
            lamps.append((entry, entity_id))
    return lamps


def _lamp_name(hass: HomeAssistant, entry: BeurerConfigEntry, entity_id: str) -> str:
    """Return the name the user sees for a lamp."""
    if (state := hass.states.get(entity_id)) and state.name:
        return state.name
    return entry.title


def _select_lamps(
    hass: HomeAssistant, llm_context: LLMContext, lamp: str | None
) -> list[tuple[BeurerConfigEntry, str]]:
    """Filter exposed lamps by a (partial) name; no name means all lamps."""
    lamps = _exposed_lamps(hass, llm_context)
    if not lamp:
        return lamps
    needle = lamp.casefold()
    return [
        (entry, entity_id)
        for entry, entity_id in lamps
        if needle in _lamp_name(hass, entry, entity_id).casefold()
        or needle in entity_id.casefold()
    ]


def _no_lamp_result(lamp: str | None) -> JsonObjectType:
    """Return the error result when no lamp matches."""
    if lamp:
        return {"success": False, "error": f"No exposed Beurer lamp matches '{lamp}'"}
    return {"success": False, "error": "No Beurer lamp is exposed to the assistant"}


class _LampServiceTool(Tool):
    """Base for tools that call one of the integration's services."""

    integration = DOMAIN
    service: str

    async def _call(
        self,
        hass: HomeAssistant,
        llm_context: LLMContext,
        args: dict[str, Any],
        service_data: dict[str, Any],
    ) -> JsonObjectType:
        """Call the service on the selected lamps."""
        lamp = args.get(ATTR_LAMP)
        lamps = _select_lamps(hass, llm_context, lamp)
        if not lamps:
            return _no_lamp_result(lamp)
        await hass.services.async_call(
            DOMAIN,
            self.service,
            {**service_data, ATTR_ENTITY_ID: [entity_id for _, entity_id in lamps]},
            blocking=True,
            context=llm_context.context,
        )
        return {
            "success": True,
            "lamps": [_lamp_name(hass, entry, eid) for entry, eid in lamps],
        }


class StartSunriseTool(_LampServiceTool):
    """Start a sunrise simulation."""

    name = f"{TOOL_PREFIX}start_sunrise"
    description = (
        "Start a sunrise simulation on a Beurer daylight lamp: the light slowly "
        "brightens from warm to daylight. Omit 'lamp' to use all lamps."
    )
    service = "start_sunrise"
    parameters = vol.Schema(
        {
            vol.Optional(ATTR_LAMP): str,
            vol.Optional("duration", default=15): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional("profile", default="natural"): vol.In(
                ["gentle", "natural", "energize", "therapy"]
            ),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Start the sunrise."""
        args = tool_input.tool_args
        return await self._call(
            hass,
            llm_context,
            args,
            {
                "duration": args.get("duration", 15),
                "profile": args.get("profile", "natural"),
            },
        )


class StartSunsetTool(_LampServiceTool):
    """Start a sunset simulation."""

    name = f"{TOOL_PREFIX}start_sunset"
    description = (
        "Start a sunset simulation on a Beurer daylight lamp: the light slowly "
        "dims and gets warmer. Omit 'lamp' to use all lamps."
    )
    service = "start_sunset"
    parameters = vol.Schema(
        {
            vol.Optional(ATTR_LAMP): str,
            vol.Optional("duration", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional("end_brightness", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Start the sunset."""
        args = tool_input.tool_args
        return await self._call(
            hass,
            llm_context,
            args,
            {
                "duration": args.get("duration", 30),
                "end_brightness": args.get("end_brightness", 0),
            },
        )


class StopSimulationTool(_LampServiceTool):
    """Stop a running sunrise or sunset."""

    name = f"{TOOL_PREFIX}stop_simulation"
    description = (
        "Stop a running sunrise or sunset simulation on a Beurer daylight lamp. "
        "Omit 'lamp' to stop it on all lamps."
    )
    service = "stop_simulation"
    parameters = vol.Schema({vol.Optional(ATTR_LAMP): str})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Stop the simulation."""
        return await self._call(hass, llm_context, tool_input.tool_args, {})


class GetTherapyStatusTool(Tool):
    """Read the daily light therapy status."""

    integration = DOMAIN
    name = f"{TOOL_PREFIX}get_therapy_status"
    description = (
        "Get today's light therapy status of Beurer daylight lamps: minutes of "
        "therapy light today and this week, the daily goal and whether it is "
        "reached, and whether a sunrise or sunset is running."
    )
    parameters = vol.Schema({vol.Optional(ATTR_LAMP): str})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Return the therapy status."""
        lamp = tool_input.tool_args.get(ATTR_LAMP)
        lamps = _select_lamps(hass, llm_context, lamp)
        if not lamps:
            return _no_lamp_result(lamp)
        result: list[JsonObjectType] = []
        for entry, entity_id in lamps:
            instance = entry.runtime_data.instance
            tracker = instance.therapy_tracker
            result.append(
                {
                    "lamp": _lamp_name(hass, entry, entity_id),
                    "today_minutes": round(tracker.today_minutes, 1),
                    "week_minutes": round(tracker.week_minutes, 1),
                    "daily_goal_minutes": tracker.daily_goal_minutes,
                    "goal_reached": tracker.goal_reached,
                    "goal_progress_percent": tracker.goal_progress_pct,
                    "simulation_running": instance.sunrise_simulation.is_running,
                }
            )
        return {"success": True, "lamps": result}  # type: ignore[dict-item]


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the Beurer tools for the Assist API."""
    if api_id != LLM_API_ASSIST or not _exposed_lamps(hass, llm_context):
        return None
    return LLMTools(
        tools=[
            StartSunriseTool(),
            StartSunsetTool(),
            StopSimulationTool(),
            GetTherapyStatusTool(),
        ]
    )
