"""Switch platform for Beurer Daylight Lamps - Adaptive Lighting Control."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import BeurerConfigEntry
from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER, VERSION, detect_model


SWITCH_DESCRIPTIONS = [
    SwitchEntityDescription(
        key="adaptive_lighting",
        translation_key="adaptive_lighting",
        icon="mdi:brightness-auto",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer Daylight Lamp switches from a config entry."""
    LOGGER.debug("Setting up Beurer switch entities")
    instance = entry.runtime_data
    name = entry.data.get("name", "Beurer Lamp")

    entities = [
        BeurerAdaptiveLightingSwitch(instance, name, entry.entry_id, desc)
        for desc in SWITCH_DESCRIPTIONS
    ]

    async_add_entities(entities)


class BeurerAdaptiveLightingSwitch(SwitchEntity, RestoreEntity):
    """Switch to control Adaptive Lighting integration for Beurer lamps.

    When enabled, allows the Adaptive Lighting integration (HACS) to control
    the lamp's color temperature throughout the day. When disabled, the lamp
    ignores Adaptive Lighting updates.

    This is useful because:
    - Daylight therapy may need consistent 5300K during sessions
    - Users may want manual control sometimes
    - Effects/moods should not be overridden by Adaptive Lighting
    """

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        beurer_instance: BeurerInstance,
        name: str,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        self._instance = beurer_instance
        self._entry_id = entry_id
        self._device_name = name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"
        self._is_on: bool = True  # Default: Adaptive Lighting enabled

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
            LOGGER.debug(
                "Restored Adaptive Lighting state: %s",
                "enabled" if self._is_on else "disabled"
            )

        # Register update callback
        self._instance.set_update_callback(self._handle_update)

        # Store the switch reference in instance for light entity access
        self._instance.adaptive_lighting_switch = self

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._instance.remove_update_callback(self._handle_update)
        if hasattr(self._instance, 'adaptive_lighting_switch'):
            delattr(self._instance, 'adaptive_lighting_switch')

    @callback
    def _handle_update(self) -> None:
        """Handle device state update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.available

    @property
    def is_on(self) -> bool:
        """Return True if Adaptive Lighting is enabled."""
        return self._is_on

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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "description": "Controls whether Adaptive Lighting can adjust this lamp",
            "therapy_mode_active": self._instance._therapy_active if hasattr(self._instance, '_therapy_active') else False,
            "current_effect": self._instance.effect if self._instance.effect != "Off" else None,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Adaptive Lighting for this lamp."""
        LOGGER.info("Enabling Adaptive Lighting for %s", self._device_name)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Adaptive Lighting for this lamp."""
        LOGGER.info("Disabling Adaptive Lighting for %s", self._device_name)
        self._is_on = False
        self.async_write_ha_state()

    def should_block_adaptive_lighting(self) -> bool:
        """Check if Adaptive Lighting should be blocked.

        Returns True if:
        - The switch is off (user disabled AL)
        - An effect is active (effects should not be overridden)
        - Therapy mode is active (therapy needs consistent light)
        """
        # Switch is off - user explicitly disabled AL
        if not self._is_on:
            return True

        # Effect is playing (not "Off") - don't override
        if self._instance.effect and self._instance.effect != "Off":
            return True

        # Therapy mode active - don't override
        if hasattr(self._instance, '_therapy_active') and self._instance._therapy_active:
            return True

        return False
