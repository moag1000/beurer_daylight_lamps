"""Light platform for Beurer Daylight Lamps."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import match_max_scale

from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER

# Model detection based on device name
MODEL_MAP = {
    "TL100": "TL100 Daylight Therapy Lamp",
    "TL50": "TL50 Daylight Therapy Lamp",
    "TL70": "TL70 Daylight Therapy Lamp",
    "TL80": "TL80 Daylight Therapy Lamp",
    "TL90": "TL90 Daylight Therapy Lamp",
}


def _detect_model(name: str | None) -> str:
    """Detect model from device name."""
    if not name:
        return "Daylight Therapy Lamp"
    name_upper = name.upper()
    for prefix, model in MODEL_MAP.items():
        if name_upper.startswith(prefix):
            return model
    return "Daylight Therapy Lamp"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer Daylight Lamp from a config entry."""
    LOGGER.debug("Setting up Beurer light entity")
    instance: BeurerInstance = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data.get("name", "Beurer Lamp")
    async_add_entities([BeurerLight(instance, name, config_entry.entry_id)])


class BeurerLight(LightEntity):
    """Representation of a Beurer Daylight Lamp."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.WHITE}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(
        self, beurer_instance: BeurerInstance, name: str, entry_id: str
    ) -> None:
        """Initialize the Beurer light."""
        self._instance = beurer_instance
        self._entry_id = entry_id
        self._device_name = name
        self._attr_unique_id = self._instance.mac

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        self._instance.set_update_callback(self._handle_update)
        await self._instance.update()

    def _handle_update(self) -> None:
        """Handle device state update."""
        self.schedule_update_ha_state(False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.is_on is not None

    @property
    def should_poll(self) -> bool:
        """No polling needed - updates via notifications."""
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
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
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._instance.color_mode == ColorMode.WHITE:
            return "Off"
        return self._instance.effect

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._instance.supported_effects

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        mode = self._instance.color_mode
        if mode == "rgb":
            return ColorMode.RGB
        if mode == "white":
            return ColorMode.WHITE
        return ColorMode.WHITE

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=_detect_model(self._device_name),
            connections={(CONNECTION_BLUETOOTH, self._instance.mac)},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        LOGGER.debug("Turning lamp on with args: %s", kwargs)

        if not kwargs:
            await self._instance.turn_on()
            return

        current_mode = self._instance.color_mode

        # Determine target mode based on parameters
        target_mode = None
        if ATTR_RGB_COLOR in kwargs or ATTR_EFFECT in kwargs:
            target_mode = ColorMode.RGB
        elif ATTR_BRIGHTNESS in kwargs and ATTR_RGB_COLOR not in kwargs:
            target_mode = ColorMode.WHITE

        # Force mode switch if needed
        if target_mode and target_mode != current_mode:
            LOGGER.debug("Mode switch required: %s -> %s", current_mode, target_mode)
            self._instance._mode = target_mode
            self._instance._light_on = False
            self._instance._color_on = False

        # Handle white mode
        if target_mode == ColorMode.WHITE:
            brightness = kwargs[ATTR_BRIGHTNESS]
            LOGGER.debug("Setting white mode with brightness %s", brightness)
            self._instance._mode = ColorMode.WHITE
            await self._instance.set_white(brightness)
            return

        # Handle RGB/effect mode
        if target_mode == ColorMode.RGB:
            self._instance._mode = ColorMode.RGB

            if ATTR_RGB_COLOR in kwargs:
                color = kwargs[ATTR_RGB_COLOR]
                LOGGER.debug("Setting RGB color %s", color)
                await self._instance.set_color(color)

                if ATTR_BRIGHTNESS in kwargs:
                    brightness = kwargs[ATTR_BRIGHTNESS]
                    LOGGER.debug("Setting color brightness %s", brightness)
                    await asyncio.sleep(0.2)
                    await self._instance.set_color_brightness(brightness)

            if ATTR_EFFECT in kwargs:
                effect = kwargs[ATTR_EFFECT]
                LOGGER.debug("Setting effect %s", effect)
                await asyncio.sleep(0.2)
                await self._instance.set_effect(effect)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._instance.turn_off()

    async def async_update(self) -> None:
        """Update the light state."""
        await self._instance.update()
