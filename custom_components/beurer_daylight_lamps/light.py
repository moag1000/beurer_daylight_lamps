"""Light platform for Beurer Daylight Lamps."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_to_rgb,
    match_max_scale,
)

from . import BeurerConfigEntry
from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER, VERSION, detect_model

# Limit parallel updates to 1 per device to prevent BLE command conflicts
PARALLEL_UPDATES = 1

# Color temperature range (in Kelvin)
# Beurer TL100 has 5300K daylight, we support warm to cool white
MIN_COLOR_TEMP_KELVIN = 2700  # Warm white
MAX_COLOR_TEMP_KELVIN = 6500  # Cool daylight


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer Daylight Lamp from a config entry."""
    LOGGER.debug("Setting up Beurer light entity")
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")
    async_add_entities([BeurerLight(instance, name, entry.entry_id)])


class BeurerLight(LightEntity):
    """Representation of a Beurer Daylight Lamp."""

    _attr_has_entity_name: bool = True
    _attr_name: str | None = None
    _attr_supported_color_modes: set[ColorMode] = {
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
        ColorMode.WHITE,
    }
    _attr_supported_features: LightEntityFeature = LightEntityFeature.EFFECT
    _attr_min_color_temp_kelvin: int = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin: int = MAX_COLOR_TEMP_KELVIN

    def __init__(
        self,
        beurer_instance: BeurerInstance,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Beurer light."""
        self._instance = beurer_instance
        self._entry_id = entry_id
        self._device_name = name
        self._attr_unique_id = format_mac(self._instance.mac)
        self._color_temp_kelvin: int | None = None  # Track color temperature

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._instance.set_update_callback(self._handle_update)
        await self._instance.update()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._instance.remove_update_callback(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle device state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Availability is based on whether we have received status from the device,
        not whether the light is on or off.
        """
        return self._instance.available

    @property
    def should_poll(self) -> bool:
        """Return False, updates via BLE notifications."""
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        if self._instance.color_mode == ColorMode.WHITE:
            return self._instance.white_brightness
        return self._instance.color_brightness

    @property
    def is_on(self) -> bool | None:
        """Return True if light is on."""
        return self._instance.is_on

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value."""
        if self._instance.rgb_color:
            return match_max_scale((255,), self._instance.rgb_color)
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        if self._instance.color_mode == ColorMode.COLOR_TEMP:
            return self._color_temp_kelvin
        return None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._instance.color_mode == ColorMode.WHITE:
            return None
        return self._instance.effect

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._instance.supported_effects

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        # If we set a color temperature, report COLOR_TEMP mode
        if self._color_temp_kelvin is not None and self._instance.color_mode == ColorMode.RGB:
            return ColorMode.COLOR_TEMP
        return self._instance.color_mode

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for device registry."""
        mac = format_mac(self._instance.mac)
        return DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=detect_model(self._device_name),
            sw_version=VERSION,
            connections={(CONNECTION_BLUETOOTH, mac)},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        LOGGER.debug("Turn on with kwargs: %s, current_mode: %s", kwargs, self._instance.color_mode)

        # No parameters - just turn on
        if not kwargs:
            await self._instance.turn_on()
            return

        # Determine target mode based on parameters
        has_color = ATTR_RGB_COLOR in kwargs
        has_color_temp = ATTR_COLOR_TEMP_KELVIN in kwargs
        has_effect = ATTR_EFFECT in kwargs
        has_brightness = ATTR_BRIGHTNESS in kwargs

        if has_color_temp:
            # Color temperature mode - convert Kelvin to RGB
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            # Clamp to supported range
            kelvin = max(MIN_COLOR_TEMP_KELVIN, min(MAX_COLOR_TEMP_KELVIN, kelvin))
            self._color_temp_kelvin = kelvin

            # Convert color temperature to RGB
            rgb = color_temperature_to_rgb(kelvin)
            LOGGER.debug("Color temp %dK -> RGB %s", kelvin, rgb)

            self._instance.set_color_mode(ColorMode.RGB)
            await self._instance.set_color(rgb)

            # Apply brightness if provided, otherwise keep current
            if has_brightness:
                await asyncio.sleep(0.2)
                await self._instance.set_color_brightness(kwargs[ATTR_BRIGHTNESS])
            elif self._instance.color_brightness:
                await asyncio.sleep(0.2)
                await self._instance.set_color_brightness(self._instance.color_brightness)

        elif has_color or has_effect:
            # RGB mode requested explicitly - clear color temp tracking
            self._color_temp_kelvin = None
            self._instance.set_color_mode(ColorMode.RGB)

            if has_color:
                await self._instance.set_color(kwargs[ATTR_RGB_COLOR])
                # If brightness is provided, use it; otherwise keep current brightness
                if has_brightness:
                    await asyncio.sleep(0.2)
                    await self._instance.set_color_brightness(kwargs[ATTR_BRIGHTNESS])
                elif self._instance.color_brightness:
                    # Restore current brightness after color change
                    await asyncio.sleep(0.2)
                    await self._instance.set_color_brightness(self._instance.color_brightness)

            if has_effect:
                await asyncio.sleep(0.2)
                await self._instance.set_effect(kwargs[ATTR_EFFECT])

        elif has_brightness:
            # Brightness only - keep current mode!
            current_mode = self._instance.color_mode
            if current_mode == ColorMode.RGB:
                # Stay in RGB mode, just adjust brightness
                await self._instance.set_color_brightness(kwargs[ATTR_BRIGHTNESS])
            elif current_mode == ColorMode.COLOR_TEMP or self._color_temp_kelvin is not None:
                # Color temp mode - stay in it, just adjust brightness
                await self._instance.set_color_brightness(kwargs[ATTR_BRIGHTNESS])
            else:
                # White mode
                await self._instance.set_white(kwargs[ATTR_BRIGHTNESS])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._instance.turn_off()

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        await self._instance.update()
