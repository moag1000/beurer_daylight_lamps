"""Time platform for Beurer Daylight Lamps (WL75/WL90 alarm times)."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import BeurerConfigEntry
    from .wl90 import AlarmItem


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up alarm time entities for wake-up lights."""
    instance = entry.runtime_data.instance
    if not instance.is_wl or instance.wl90 is None:
        return
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")
    async_add_entities(
        BeurerAlarmTime(coordinator, name, slot)
        for slot in range(len(instance.wl90.alarms))
    )


class BeurerAlarmTime(CoordinatorEntity[BeurerDataUpdateCoordinator], TimeEntity):
    """Wake-up time of one alarm slot."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        slot: int,
    ) -> None:
        """Initialize the alarm time entity."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self._slot = slot
        self._attr_translation_key = f"alarm_{slot + 1}_time"
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_alarm_{slot + 1}_time"

    @property
    def _alarm(self) -> AlarmItem | None:
        """Return the alarm of this slot."""
        wl = self._instance.wl90
        if wl is None or self._slot >= len(wl.alarms):
            return None
        return wl.alarms[self._slot]

    @property
    def available(self) -> bool:
        """Return True if the lamp is reachable and the slot exists."""
        return self._instance.available and self._alarm is not None

    @property
    def native_value(self) -> time | None:
        """Return the alarm time."""
        alarm = self._alarm
        if alarm is None:
            return None
        return time(alarm.hour, alarm.minute)

    async def async_set_value(self, value: time) -> None:
        """Change the alarm time and write the alarm to the lamp."""
        alarm = self._alarm
        wl = self._instance.wl90
        if alarm is None or wl is None:
            return
        alarm.hour = value.hour
        alarm.minute = value.minute
        LOGGER.debug(
            "Setting alarm %d on %s to %02d:%02d",
            self._slot,
            self._instance.mac,
            value.hour,
            value.minute,
        )
        await wl.sync_alarm(self._slot, alarm)
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
