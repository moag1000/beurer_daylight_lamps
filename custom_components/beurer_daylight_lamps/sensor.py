"""Sensor platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTime, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BeurerConfigEntry
from .const import DOMAIN, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_notification",
        translation_key="last_notification",
        icon="mdi:bluetooth-transfer",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
    ),
)

# Therapy tracking sensors (lifestyle/wellness feature, NOT medical)
THERAPY_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="therapy_today",
        translation_key="therapy_today",
        icon="mdi:sun-clock",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="therapy_week",
        translation_key="therapy_week",
        icon="mdi:calendar-week",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="therapy_progress",
        translation_key="therapy_progress",
        icon="mdi:progress-check",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

# Connection health sensors (diagnostic)
CONNECTION_HEALTH_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="reconnect_count",
        translation_key="reconnect_count",
        icon="mdi:connection",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="command_success_rate",
        translation_key="command_success_rate",
        icon="mdi:check-network",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="connection_uptime",
        translation_key="connection_uptime",
        icon="mdi:timer-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
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
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")

    entities: list[SensorEntity] = [
        BeurerSensor(coordinator, name, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    # Add therapy tracking sensors
    entities.extend([
        BeurerTherapySensor(coordinator, name, description)
        for description in THERAPY_SENSOR_DESCRIPTIONS
    ])
    # Add connection health sensors
    entities.extend([
        BeurerConnectionHealthSensor(coordinator, name, description)
        for description in CONNECTION_HEALTH_SENSOR_DESCRIPTIONS
    ])
    async_add_entities(entities)


class BeurerSensor(CoordinatorEntity[BeurerDataUpdateCoordinator], SensorEntity):
    """Representation of a Beurer sensor."""

    _attr_has_entity_name = True

    # Prevent high-frequency diagnostic data from bloating the database
    # RSSI changes with every BLE advertisement (multiple times per second)
    _unrecorded_attributes = frozenset({"last_seen", "raw_value"})

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"

    @property
    def native_value(self) -> int | str | None:
        """Return the sensor value."""
        if self.entity_description.key == "rssi":
            return self._instance.rssi
        elif self.entity_description.key == "last_notification":
            return self._instance.last_raw_notification
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


class BeurerTherapySensor(CoordinatorEntity[BeurerDataUpdateCoordinator], SensorEntity):
    """Sensor for tracking light exposure.

    NOTE: This is a lifestyle/wellness feature for personal tracking.
    It is NOT a medical device and should not be used for medical purposes.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the therapy sensor."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        key = self.entity_description.key
        if key == "therapy_today":
            return round(self._instance.therapy_today_minutes, 1)
        elif key == "therapy_week":
            return round(self._instance.therapy_week_minutes, 1)
        elif key == "therapy_progress":
            return self._instance.therapy_goal_progress_pct
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


class BeurerConnectionHealthSensor(CoordinatorEntity[BeurerDataUpdateCoordinator], SensorEntity):
    """Sensor for monitoring connection health metrics.

    Provides diagnostic information about BLE connection stability:
    - Reconnect count: Number of reconnections since startup
    - Command success rate: Percentage of successful BLE commands
    - Connection uptime: Seconds since current connection established
    """

    _attr_has_entity_name = True

    # Prevent high-frequency updates from bloating the database
    _unrecorded_attributes = frozenset({"total_commands"})

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the connection health sensor."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        key = self.entity_description.key
        if key == "reconnect_count":
            return self._instance.reconnect_count
        elif key == "command_success_rate":
            return self._instance.command_success_rate
        elif key == "connection_uptime":
            return self._instance.connection_uptime_seconds
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Return additional state attributes."""
        if self.entity_description.key == "command_success_rate":
            return {"total_commands": self._instance.total_commands}
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # These metrics are always available (they track from startup)
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
