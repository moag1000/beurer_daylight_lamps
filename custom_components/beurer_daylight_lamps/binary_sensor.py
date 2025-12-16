"""Binary sensor platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BeurerConfigEntry
from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, VERSION, detect_model

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="connected",
        name="Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="ble_available",
        name="Bluetooth reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer binary sensors from a config entry."""
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")

    entities = [
        BeurerBinarySensor(instance, name, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class BeurerBinarySensor(BinarySensorEntity):
    """Representation of a Beurer binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        instance: BeurerInstance,
        device_name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self._instance = instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(instance.mac)}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        if self.entity_description.key == "connected":
            return self._instance.is_connected
        elif self.entity_description.key == "ble_available":
            return self._instance.ble_available
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Binary sensors for connectivity should always be available.
        """
        return True

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
