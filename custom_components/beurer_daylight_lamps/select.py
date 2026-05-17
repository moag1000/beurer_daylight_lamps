"""Select platform for Beurer Daylight Lamps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEFAULT_THERAPY_USER,
    DOMAIN,
    LOGGER,
    SUPPORTED_EFFECTS,
    THERAPY_USER_UNKNOWN,
    VERSION,
    detect_model,
)
from .coordinator import BeurerDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import BeurerConfigEntry

SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="effect",
        translation_key="effect",
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

    entities: list[SelectEntity] = [
        BeurerEffectSelect(coordinator, name, SELECT_DESCRIPTIONS[0]),
        BeurerTherapyUserSelect(hass, coordinator, name, entry),
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


class BeurerTherapyUserSelect(
    CoordinatorEntity[BeurerDataUpdateCoordinator], SelectEntity, RestoreEntity
):
    """Selects which HA person is currently doing therapy on this lamp."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account"
    _attr_translation_key = "therapy_user"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        entry: BeurerConfigEntry,
    ) -> None:
        """Initialize the therapy user select."""
        super().__init__(coordinator)
        self._hass = hass
        self._instance = coordinator.instance
        self._device_name = device_name
        self._entry = entry
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_therapy_user"
        self._current: str = THERAPY_USER_UNKNOWN

    @property
    def options(self) -> list[str]:
        """Return list of options: unknown sentinel + all HA person entity_ids."""
        persons = sorted(s.entity_id for s in self._hass.states.async_all("person"))
        return [THERAPY_USER_UNKNOWN, *persons]

    @property
    def current_option(self) -> str:
        """Return the currently selected therapy user."""
        return self._current

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
        """Restore last known state on startup."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self.options:
            self._current = last.state
        else:
            default = self._entry.options.get(CONF_DEFAULT_THERAPY_USER)
            if default and default in self.options:
                self._current = default

    @property
    def available(self) -> bool:
        """Always available — attribution is HA-side state, not lamp state."""
        return True

    async def async_select_option(self, option: str) -> None:
        """Change the active therapy user."""
        if option not in self.options:
            raise HomeAssistantError(f"Invalid therapy user: {option}")
        self._current = option
        self.async_write_ha_state()
