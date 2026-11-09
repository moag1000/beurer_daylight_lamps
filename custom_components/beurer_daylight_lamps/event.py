"""Event platform for Beurer Daylight Lamps.

Exposes momentary lamp events (timer finished, sunrise finished, ...) as an
event entity, so automations can react to them and the integration triggers
in trigger.py can target them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)

from .const import DOMAIN, LAMP_EVENT_TYPES, VERSION, detect_model

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .beurer_daylight_lamps import BeurerInstance
    from .data import BeurerConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Beurer lamp event entity."""
    name = entry.data.get("name", "Beurer Lamp")
    async_add_entities([BeurerLampEvent(entry.runtime_data.instance, name)])


class BeurerLampEvent(EventEntity):
    """Momentary lamp events (timer, sleep timer, sunrise, sunset)."""

    _attr_has_entity_name = True
    _attr_translation_key = "lamp_event"
    _attr_event_types = LAMP_EVENT_TYPES
    _attr_should_poll = False

    def __init__(self, instance: BeurerInstance, device_name: str) -> None:
        """Initialize the event entity."""
        self._instance = instance
        self._device_name = device_name
        self._attr_unique_id = f"{format_mac(instance.mac)}_lamp_event"

    async def async_added_to_hass(self) -> None:
        """Listen for lamp events."""
        await super().async_added_to_hass()
        self.async_on_remove(self._instance.add_event_listener(self._handle_event))

    @callback
    def _handle_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Record a lamp event."""
        self._trigger_event(event_type, data)
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        mac = format_mac(self._instance.mac)
        return DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=detect_model(self._device_name),
            sw_version=VERSION,
            connections={(CONNECTION_BLUETOOTH, mac)},
        )
