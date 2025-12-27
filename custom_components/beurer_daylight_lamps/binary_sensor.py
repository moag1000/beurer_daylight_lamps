"""Binary sensor platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BeurerConfigEntry
from .const import DOMAIN, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="ble_available",
        translation_key="ble_available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Therapy goal sensor (lifestyle/wellness feature, NOT medical)
THERAPY_BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="therapy_goal_reached",
        translation_key="therapy_goal_reached",
        icon="mdi:check-circle",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")

    entities: list[BinarySensorEntity] = [
        BeurerBinarySensor(coordinator, name, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    # Add therapy goal sensor
    entities.extend([
        BeurerTherapyBinarySensor(coordinator, name, description)
        for description in THERAPY_BINARY_SENSOR_DESCRIPTIONS
    ])
    async_add_entities(entities)


class BeurerBinarySensor(CoordinatorEntity[BeurerDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a Beurer binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"

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


class BeurerTherapyBinarySensor(CoordinatorEntity[BeurerDataUpdateCoordinator], BinarySensorEntity):
    """Binary sensor for tracking therapy goal completion.

    NOTE: This is a lifestyle/wellness feature for personal tracking.
    It is NOT a medical device and should not be used for medical purposes.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the therapy binary sensor."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if daily therapy goal is reached."""
        if self.entity_description.key == "therapy_goal_reached":
            return self._instance.therapy_goal_reached
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Always available as tracking persists

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
