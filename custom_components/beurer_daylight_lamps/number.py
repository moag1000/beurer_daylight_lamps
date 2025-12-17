"""Number platform for Beurer Daylight Lamps."""
from __future__ import annotations

from homeassistant.components.light import ColorMode
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BeurerConfigEntry
from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER, VERSION, detect_model, CMD_TIMER

NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="white_brightness",
        name="White brightness",
        icon="mdi:brightness-6",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    NumberEntityDescription(
        key="color_brightness",
        name="Color brightness",
        icon="mdi:brightness-7",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer number entities from a config entry."""
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")

    entities: list[NumberEntity] = [
        BeurerBrightnessNumber(instance, name, description)
        for description in NUMBER_DESCRIPTIONS
    ]
    # Add timer entity
    entities.append(BeurerTimerNumber(instance, name))
    async_add_entities(entities)


class BeurerBrightnessNumber(NumberEntity):
    """Representation of a Beurer brightness number."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        instance: BeurerInstance,
        device_name: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        self._instance = instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(instance.mac)}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current brightness value (0-100%)."""
        if self.entity_description.key == "white_brightness":
            brightness = self._instance.white_brightness
        else:
            brightness = self._instance.color_brightness

        if brightness is None:
            return None
        # Convert from 0-255 to 0-100
        return round(brightness / 255 * 100)

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

    async def async_set_native_value(self, value: float) -> None:
        """Set the brightness value."""
        # Convert from 0-100 to 0-255
        brightness = int(value / 100 * 255)
        LOGGER.debug("Setting %s to %d%% (%d/255)", self.entity_description.key, value, brightness)

        if self.entity_description.key == "white_brightness":
            await self._instance.set_white(brightness)
        else:
            await self._instance.set_color_brightness(brightness)


class BeurerTimerNumber(NumberEntity):
    """Representation of a Beurer timer number.

    Timer only works when the lamp is in RGB mode.
    Shows unavailable when in white mode.
    """

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Timer"

    def __init__(
        self,
        instance: BeurerInstance,
        device_name: str,
    ) -> None:
        """Initialize the timer number."""
        self._instance = instance
        self._device_name = device_name
        self._attr_unique_id = f"{format_mac(instance.mac)}_timer"
        self._last_set_value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return the last set timer value or None."""
        return self._last_set_value

    @property
    def available(self) -> bool:
        """Return True only when device is available AND in RGB mode.

        Timer command (0x3E) only works in RGB mode per protocol specification.
        """
        if not self._instance.available:
            return False
        # Timer only works in RGB mode
        return self._instance.color_mode == ColorMode.RGB

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

    async def async_set_native_value(self, value: float) -> None:
        """Set the timer value in minutes."""
        minutes = int(value)
        LOGGER.info("Setting timer to %d minutes", minutes)

        # Send timer command: 0x3E followed by minutes
        success = await self._instance._send_packet([CMD_TIMER, minutes])
        if success:
            self._last_set_value = value
            LOGGER.info("Timer set to %d minutes", minutes)
        else:
            LOGGER.error("Failed to set timer to %d minutes", minutes)
