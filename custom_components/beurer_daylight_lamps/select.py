"""Select platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BeurerConfigEntry
from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER, VERSION, detect_model, SUPPORTED_EFFECTS

SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="effect",
        name="Effect",
        icon="mdi:palette",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer select entities from a config entry."""
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")

    entities = [
        BeurerEffectSelect(instance, name, SELECT_DESCRIPTIONS[0])
    ]
    async_add_entities(entities)


class BeurerEffectSelect(SelectEntity):
    """Representation of a Beurer effect select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        instance: BeurerInstance,
        device_name: str,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        self._instance = instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(instance.mac)}_{description.key}"
        self._attr_options = list(SUPPORTED_EFFECTS)

    @property
    def current_option(self) -> str | None:
        """Return current selected effect."""
        return self._instance.effect

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.available

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

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._instance.set_update_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._instance.remove_update_callback(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle device state update."""
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected effect."""
        LOGGER.debug("Setting effect to %s", option)
        await self._instance.set_effect(option)
