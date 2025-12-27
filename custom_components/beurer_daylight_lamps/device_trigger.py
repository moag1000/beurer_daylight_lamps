"""Device triggers for Beurer Daylight Lamps."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_ON,
    STATE_OFF,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# Trigger types
TRIGGER_TYPE_TURNED_ON = "turned_on"
TRIGGER_TYPE_TURNED_OFF = "turned_off"
TRIGGER_TYPE_THERAPY_GOAL_REACHED = "therapy_goal_reached"
TRIGGER_TYPE_CONNECTION_LOST = "connection_lost"
TRIGGER_TYPE_CONNECTION_RESTORED = "connection_restored"

TRIGGER_TYPES = {
    TRIGGER_TYPE_TURNED_ON,
    TRIGGER_TYPE_TURNED_OFF,
    TRIGGER_TYPE_THERAPY_GOAL_REACHED,
    TRIGGER_TYPE_CONNECTION_LOST,
    TRIGGER_TYPE_CONNECTION_RESTORED,
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Beurer lamps.

    Args:
        hass: Home Assistant instance
        device_id: Device ID to get triggers for

    Returns:
        List of available triggers for the device
    """
    triggers: list[dict[str, Any]] = []
    entity_registry = er.async_get(hass)

    # Get all entities for this device
    entries = er.async_entries_for_device(entity_registry, device_id)

    for entry in entries:
        if entry.domain == "light" and entry.platform == DOMAIN:
            # Light on/off triggers
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: TRIGGER_TYPE_TURNED_ON,
                }
            )
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: TRIGGER_TYPE_TURNED_OFF,
                }
            )

        elif entry.domain == "binary_sensor" and entry.platform == DOMAIN:
            if "therapy_goal_reached" in entry.entity_id:
                # Therapy goal reached trigger
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: TRIGGER_TYPE_THERAPY_GOAL_REACHED,
                    }
                )
            elif "connected" in entry.entity_id:
                # Connection triggers
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: TRIGGER_TYPE_CONNECTION_LOST,
                    }
                )
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: TRIGGER_TYPE_CONNECTION_RESTORED,
                    }
                )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger.

    Args:
        hass: Home Assistant instance
        config: Trigger configuration
        action: Action to call when trigger fires
        trigger_info: Trigger information

    Returns:
        Callback to remove the trigger
    """
    trigger_type = config[CONF_TYPE]
    entity_id = config[CONF_ENTITY_ID]

    # Map trigger types to state changes
    if trigger_type == TRIGGER_TYPE_TURNED_ON:
        to_state = STATE_ON
        from_state = None
    elif trigger_type == TRIGGER_TYPE_TURNED_OFF:
        to_state = STATE_OFF
        from_state = None
    elif trigger_type == TRIGGER_TYPE_THERAPY_GOAL_REACHED:
        to_state = STATE_ON
        from_state = STATE_OFF
    elif trigger_type == TRIGGER_TYPE_CONNECTION_LOST:
        to_state = STATE_OFF
        from_state = STATE_ON
    elif trigger_type == TRIGGER_TYPE_CONNECTION_RESTORED:
        to_state = STATE_ON
        from_state = STATE_OFF
    else:
        return lambda: None

    state_config = {
        CONF_PLATFORM: "state",
        CONF_ENTITY_ID: entity_id,
        state_trigger.CONF_TO: to_state,
    }

    if from_state is not None:
        state_config[state_trigger.CONF_FROM] = from_state

    state_config = await state_trigger.async_validate_trigger_config(hass, state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities.

    Args:
        hass: Home Assistant instance
        config: Trigger configuration

    Returns:
        Dictionary with extra fields schema
    """
    return {
        "extra_fields": vol.Schema({})
    }
