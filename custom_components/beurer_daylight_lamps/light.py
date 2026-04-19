"""Light platform for Beurer Daylight Lamps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (  # type: ignore[attr-defined]
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import (
    color_temperature_to_rgb,
    match_max_scale,
)

from .const import DOMAIN, LOGGER, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import BeurerConfigEntry

# Limit parallel updates to 1 per device to prevent BLE command conflicts
PARALLEL_UPDATES = 1


@dataclass
class BeurerLightExtraStoredData(ExtraStoredData):
    """Extra stored data for Beurer light entity.

    Stores color temperature across HA restarts since it's simulated
    via RGB and not stored on the device itself.
    """

    color_temp_kelvin: int | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {"color_temp_kelvin": self.color_temp_kelvin}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> BeurerLightExtraStoredData | None:
        """Initialize extra stored data from a dict."""
        try:
            return cls(color_temp_kelvin=restored.get("color_temp_kelvin"))
        except (KeyError, TypeError):
            return None


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


class BeurerLight(
    CoordinatorEntity[BeurerDataUpdateCoordinator], RestoreEntity, LightEntity
):
    """Representation of a Beurer Daylight Lamp.

    Uses RestoreEntity to persist color temperature across HA restarts,
    since color temp is simulated via RGB and not stored on the device.
    """

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

        # Restore color temperature from previous state
        if (
            (extra_data := await self.async_get_last_extra_data()) is not None
            and (restored := BeurerLightExtraStoredData.from_dict(extra_data.as_dict()))
            is not None
            and restored.color_temp_kelvin is not None
        ):
            self._color_temp_kelvin = restored.color_temp_kelvin
            LOGGER.debug(
                "Restored color temperature: %dK for %s",
                self._color_temp_kelvin,
                self._instance.mac,
            )

        await self._instance.update()

    @property
    def extra_restore_state_data(self) -> BeurerLightExtraStoredData:
        """Return entity specific state data to be restored."""
        return BeurerLightExtraStoredData(color_temp_kelvin=self._color_temp_kelvin)

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Stays available after first successful connection so commands
        can trigger reconnection transparently via _send_packet.
        """
        return self._instance.available

    @property
    def assumed_state(self) -> bool:
        """Return True when not connected (state may be stale)."""
        return not self._instance.is_connected

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

    async def _handle_color_temp(
        self, kelvin: int, brightness: int | None, has_brightness: bool
    ) -> None:
        """Handle color temperature turn-on mode."""
        kelvin = max(MIN_COLOR_TEMP_KELVIN, min(MAX_COLOR_TEMP_KELVIN, kelvin))
        self._color_temp_kelvin = kelvin

        if kelvin >= WHITE_MODE_THRESHOLD_KELVIN:
            LOGGER.debug(
                "Color temp %dK >= %dK, using native white mode "
                "(current mode=%s, color_on=%s)",
                kelvin,
                WHITE_MODE_THRESHOLD_KELVIN,
                self._instance.color_mode,
                self._instance.color_on,
            )
            await self._instance.set_white(
                brightness if has_brightness else self._instance.white_brightness
            )
        else:
            ct_rgb_float = color_temperature_to_rgb(kelvin)
            ct_rgb: tuple[int, int, int] = (
                int(ct_rgb_float[0]),
                int(ct_rgb_float[1]),
                int(ct_rgb_float[2]),
            )
            LOGGER.debug("Color temp %dK -> RGB %s", kelvin, ct_rgb)
            await self._instance.set_color_with_brightness(
                ct_rgb,
                brightness if has_brightness else self._instance.color_brightness,
            )

    async def _handle_brightness_only(self, brightness: int | None) -> None:
        """Handle brightness-only turn-on mode."""
        if (
            self._color_temp_kelvin is not None
            or self._instance.color_mode == ColorMode.RGB
            or self._instance.color_on
        ):
            await self._instance.set_color_brightness(brightness)
        else:
            await self._instance.set_white(brightness)

    def _is_white_rgb(self, rgb: tuple[int, int, int]) -> bool:
        """Check if an RGB value is white-ish (from HomeKit/Siri)."""
        r, g, b = rgb[0], rgb[1], rgb[2]
        min_val = min(r, g, b)
        max_val = max(r, g, b)
        return min_val >= 200 and (max_val - min_val) <= 55

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        LOGGER.debug(
            "Turn on with kwargs: %s, current_mode: %s, is_on: %s",
            kwargs,
            self._instance.color_mode,
            self._instance.is_on,
        )

        if not kwargs:
            await self._instance.turn_on()
            return

        has_color = ATTR_RGB_COLOR in kwargs
        has_color_temp = ATTR_COLOR_TEMP_KELVIN in kwargs
        has_effect = ATTR_EFFECT in kwargs
        has_brightness = ATTR_BRIGHTNESS in kwargs
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        # Detect "white" RGB values from HomeKit/Siri
        if has_color and not has_color_temp and not has_effect:
            rgb = kwargs[ATTR_RGB_COLOR]
            if self._is_white_rgb(rgb):
                LOGGER.debug(
                    "Detected white-ish RGB %s, using native white mode "
                    "(current mode=%s, color_on=%s)",
                    rgb,
                    self._instance.color_mode,
                    self._instance.color_on,
                )
                self._color_temp_kelvin = WHITE_MODE_THRESHOLD_KELVIN
                await self._instance.set_white(
                    brightness if has_brightness else self._instance.white_brightness
                )
                return

        if has_color_temp:
            await self._handle_color_temp(
                kwargs[ATTR_COLOR_TEMP_KELVIN], brightness, has_brightness
            )
        elif has_color:
            self._color_temp_kelvin = None
            await self._instance.set_color_with_brightness(
                kwargs[ATTR_RGB_COLOR],
                brightness if has_brightness else self._instance.color_brightness,
            )
        elif has_effect:
            self._color_temp_kelvin = None
            await self._instance.set_effect(kwargs[ATTR_EFFECT])
            if has_brightness:
                await self._instance.set_color_brightness(brightness)
        elif has_brightness:
            await self._handle_brightness_only(brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._instance.turn_off()

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        await self._instance.update()
