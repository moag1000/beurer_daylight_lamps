"""Button platform for Beurer Daylight Lamps."""
from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BeurerConfigEntry
from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER, VERSION, detect_model

BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="identify",
        translation_key="identify",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ButtonEntityDescription(
        key="reconnect",
        translation_key="reconnect",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer buttons from a config entry."""
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")

    entities = [
        BeurerButton(instance, name, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)


class BeurerButton(ButtonEntity):
    """Representation of a Beurer button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        instance: BeurerInstance,
        device_name: str,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        self._instance = instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(instance.mac)}_{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Reconnect button should always be available
        if self.entity_description.key == "reconnect":
            return True
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

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.key == "identify":
            await self._identify()
        elif self.entity_description.key == "reconnect":
            await self._reconnect()

    async def _identify(self) -> None:
        """Flash the lamp to identify it."""
        LOGGER.info("Identifying lamp %s", self._instance.mac)

        # Store current state
        was_on = self._instance.is_on
        current_brightness = self._instance.color_brightness or self._instance.white_brightness

        # Flash sequence: blink 3 times
        for _ in range(3):
            await self._instance.turn_off()
            await asyncio.sleep(0.3)
            await self._instance.turn_on()
            await asyncio.sleep(0.3)

        # Restore previous state
        if not was_on:
            await self._instance.turn_off()

    async def _reconnect(self) -> None:
        """Force reconnection to the device."""
        LOGGER.info("Forcing reconnection to %s", self._instance.mac)
        await self._instance.disconnect()
        await asyncio.sleep(0.5)
        await self._instance.connect()
