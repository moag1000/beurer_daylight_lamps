"""Sensor platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
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

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rssi",
        name="Signal strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_raw_notification",
        name="Last raw notification",
        icon="mdi:bluetooth-transfer",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_unknown_notification",
        name="Last unknown notification",
        icon="mdi:help-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_notification_version",
        name="Last notification version",
        icon="mdi:numeric",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heartbeat_count",
        name="Heartbeat count",
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer sensors from a config entry."""
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")

    entities = [
        BeurerSensor(instance, name, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class BeurerSensor(SensorEntity):
    """Representation of a Beurer sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        instance: BeurerInstance,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._instance = instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(instance.mac)}_{description.key}"

    @property
    def native_value(self) -> int | str | None:
        """Return the sensor value."""
        key = self.entity_description.key
        if key == "rssi":
            return self._instance.rssi
        if key == "last_raw_notification":
            return self._instance.last_raw_notification
        if key == "last_unknown_notification":
            return self._instance.last_unknown_notification
        if key == "last_notification_version":
            return self._instance.last_notification_version
        if key == "heartbeat_count":
            return self._instance.heartbeat_count
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Availability is based on connection state, not power state.
        """
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
