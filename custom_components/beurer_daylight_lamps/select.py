"""Select platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BeurerConfigEntry
from .const import DOMAIN, LOGGER, VERSION, detect_model, SUPPORTED_EFFECTS
from .coordinator import BeurerDataUpdateCoordinator

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
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")

    entities = [
        BeurerEffectSelect(coordinator, name, SELECT_DESCRIPTIONS[0])
    ]
    async_add_entities(entities)


class BeurerEffectSelect(CoordinatorEntity[BeurerDataUpdateCoordinator], SelectEntity):
    """Representation of a Beurer effect select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"
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

    async def async_select_option(self, option: str) -> None:
        """Change the selected effect."""
        LOGGER.debug("Setting effect to %s", option)
        await self._instance.set_effect(option)
