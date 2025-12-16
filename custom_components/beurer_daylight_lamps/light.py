"""Light platform for Beurer Daylight Lamps."""
from __future__ import annotations

import asyncio
from typing import Any, Final

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import match_max_scale

from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER

# Model detection based on device name
MODEL_MAP: Final[dict[str, str]] = {
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

    _attr_has_entity_name: bool = True
    _attr_name: str | None = None
    _attr_supported_color_modes: set[ColorMode] = {ColorMode.RGB, ColorMode.WHITE}
    _attr_supported_features: LightEntityFeature = LightEntityFeature.EFFECT

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
        self._attr_unique_id = self._instance.mac

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._instance.set_update_callback(self._handle_update)
        await self._instance.update()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._instance.set_update_callback(None)

    @callback
    def _handle_update(self) -> None:
        """Handle device state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.is_on is not None

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
        return self._instance.color_mode

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=_detect_model(self._device_name),
            connections={(CONNECTION_BLUETOOTH, self._instance.mac)},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        LOGGER.debug("Turn on with kwargs: %s", kwargs)

        # No parameters - just turn on
        if not kwargs:
            await self._instance.turn_on()
            return

        # Determine target mode based on parameters
        has_color = ATTR_RGB_COLOR in kwargs
        has_effect = ATTR_EFFECT in kwargs
        has_brightness = ATTR_BRIGHTNESS in kwargs

        if has_color or has_effect:
            # RGB mode
            self._instance._mode = ColorMode.RGB

            if has_color:
                await self._instance.set_color(kwargs[ATTR_RGB_COLOR])
                if has_brightness:
                    await asyncio.sleep(0.2)
                    await self._instance.set_color_brightness(kwargs[ATTR_BRIGHTNESS])

            if has_effect:
                await asyncio.sleep(0.2)
                await self._instance.set_effect(kwargs[ATTR_EFFECT])

        elif has_brightness:
            # White mode with brightness
            self._instance._mode = ColorMode.WHITE
            await self._instance.set_white(kwargs[ATTR_BRIGHTNESS])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._instance.turn_off()

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        await self._instance.update()
