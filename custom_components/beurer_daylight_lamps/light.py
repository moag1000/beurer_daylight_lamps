"""Light platform for Beurer Daylight Lamps."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (  # type: ignore[attr-defined]
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import (
    color_temperature_to_rgb,
    match_max_scale,
)

from . import BeurerConfigEntry
from .const import DOMAIN, LOGGER, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator

# Limit parallel updates to 1 per device to prevent BLE command conflicts
PARALLEL_UPDATES = 1

# Color temperature range (in Kelvin)
# Beurer TL100 has 5300K daylight, we support warm to cool white
MIN_COLOR_TEMP_KELVIN = 2700  # Warm white
MAX_COLOR_TEMP_KELVIN = 6500  # Cool daylight

# Threshold for switching to native white mode (Kelvin)
# When color temp is >= this value, use the lamp's native white mode
# The TL100's white mode is optimized 5300K daylight therapy light
WHITE_MODE_THRESHOLD_KELVIN = 5000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer Daylight Lamp from a config entry."""
    LOGGER.debug("Setting up Beurer light entity")
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")
    async_add_entities([BeurerLight(coordinator, name, entry.entry_id)])


class BeurerLight(CoordinatorEntity[BeurerDataUpdateCoordinator], LightEntity):
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

    # Prevent high-frequency diagnostic data from bloating the database
    _unrecorded_attributes = frozenset({"last_notification", "ble_rssi"})

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Beurer light."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._entry_id = entry_id
        self._device_name = name
        self._attr_unique_id = format_mac(self._instance.mac)
        self._color_temp_kelvin: int | None = None  # Track color temperature

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self._instance.update()

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
        # Only return RGB when in color mode
        if self._instance.color_mode != ColorMode.RGB:
            return None
        scaled = match_max_scale((255,), self._instance.rgb_color)
        return (scaled[0], scaled[1], scaled[2])

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
        # If native white mode is active, report WHITE
        if self._instance.color_mode == ColorMode.WHITE:
            return ColorMode.WHITE
        # If we set a color temperature (simulated via RGB), report COLOR_TEMP
        if self._color_temp_kelvin is not None:
            return ColorMode.COLOR_TEMP
        # Otherwise report the instance's mode (RGB)
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
        LOGGER.debug(
            "Turn on with kwargs: %s, current_mode: %s, is_on: %s",
            kwargs,
            self._instance.color_mode,
            self._instance.is_on,
        )

        # No parameters - just turn on with current settings
        if not kwargs:
            await self._instance.turn_on()
            return

        # Determine target mode based on parameters
        has_color = ATTR_RGB_COLOR in kwargs
        has_color_temp = ATTR_COLOR_TEMP_KELVIN in kwargs
        has_effect = ATTR_EFFECT in kwargs
        has_brightness = ATTR_BRIGHTNESS in kwargs

        # Get brightness value (use provided or keep current)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        # Detect "white" RGB values from HomeKit/Siri
        # When Siri says "cold white", HomeKit sends RGB (255,255,255) or similar
        # high-white values instead of color temperature
        if has_color and not has_color_temp and not has_effect:
            rgb = kwargs[ATTR_RGB_COLOR]
            r, g, b = rgb[0], rgb[1], rgb[2]
            # Check if this is a "white-ish" color (all components high and similar)
            min_val = min(r, g, b)
            max_val = max(r, g, b)
            # If all RGB values are >= 200 and within 55 of each other, treat as white
            if min_val >= 200 and (max_val - min_val) <= 55:
                LOGGER.debug(
                    "Detected white-ish RGB %s from HomeKit, using native white mode",
                    rgb
                )
                await self._instance.set_white(
                    brightness if has_brightness else self._instance.white_brightness
                )
                return

        if has_color_temp:
            # Color temperature mode
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            # Clamp to supported range
            kelvin = max(MIN_COLOR_TEMP_KELVIN, min(MAX_COLOR_TEMP_KELVIN, kelvin))
            self._color_temp_kelvin = kelvin

            # For high color temperatures (>= 5000K), use native white mode
            # This gives the best daylight therapy light quality
            if kelvin >= WHITE_MODE_THRESHOLD_KELVIN:
                LOGGER.debug(
                    "Color temp %dK >= %dK, using native white mode",
                    kelvin, WHITE_MODE_THRESHOLD_KELVIN
                )
                await self._instance.set_white(
                    brightness if has_brightness else self._instance.white_brightness
                )
            else:
                # For lower color temperatures, simulate via RGB
                ct_rgb_float = color_temperature_to_rgb(kelvin)
                ct_rgb: tuple[int, int, int] = (
                    int(ct_rgb_float[0]),
                    int(ct_rgb_float[1]),
                    int(ct_rgb_float[2]),
                )
                LOGGER.debug("Color temp %dK -> RGB %s", kelvin, ct_rgb)

                # Use combined method to set color + brightness atomically
                await self._instance.set_color_with_brightness(
                    ct_rgb,
                    brightness if has_brightness else self._instance.color_brightness,
                )

        elif has_color:
            # RGB color mode - clear color temp tracking
            self._color_temp_kelvin = None

            # Use combined method to set color + brightness atomically
            await self._instance.set_color_with_brightness(
                kwargs[ATTR_RGB_COLOR],
                brightness if has_brightness else self._instance.color_brightness,
            )

        elif has_effect:
            # Effect mode - clear color temp tracking
            self._color_temp_kelvin = None
            await self._instance.set_effect(kwargs[ATTR_EFFECT])
            # Apply brightness after effect if provided
            if has_brightness:
                await self._instance.set_color_brightness(brightness)

        elif has_brightness:
            # Brightness only - determine mode from current state
            if self._color_temp_kelvin is not None:
                # We're in color temp mode (simulated via RGB)
                await self._instance.set_color_brightness(brightness)
            elif self._instance.color_mode == ColorMode.RGB or self._instance.color_on:
                # In RGB mode (use public property instead of private _color_on)
                await self._instance.set_color_brightness(brightness)
            else:
                # In White mode
                await self._instance.set_white(brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._instance.turn_off()

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        await self._instance.update()
