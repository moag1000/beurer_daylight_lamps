"""Switch platform for Beurer Daylight Lamps - Adaptive Lighting & Device Settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, VERSION, detect_model
from .coordinator import BeurerDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import BeurerConfigEntry

SWITCH_DESCRIPTIONS = [
    SwitchEntityDescription(
        key="adaptive_lighting",
        translation_key="adaptive_lighting",
    ),
]

# Device hardware switches (discovered from APK reverse engineering)
DEVICE_SWITCH_DESCRIPTIONS = [
    SwitchEntityDescription(
        key="feedback_sound",
        translation_key="feedback_sound",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="fade",
        translation_key="fade",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer Daylight Lamp switches from a config entry."""
    LOGGER.debug("Setting up Beurer switch entities")
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")

    entities: list[SwitchEntity] = [
        BeurerAdaptiveLightingSwitch(coordinator, name, entry.entry_id, desc)
        for desc in SWITCH_DESCRIPTIONS
    ]
    # Add device hardware switches (feedback sound, fade)
    # Note: WL75 does not support the fade hardware setting
    instance = entry.runtime_data.instance
    for desc in DEVICE_SWITCH_DESCRIPTIONS:
        if desc.key == "fade" and instance.is_wl75:
            continue
        entities.append(BeurerDeviceSwitch(coordinator, name, desc))

    # Add alarm switches for WL models (WL75 has 2 slots, WL90 has 3 slots)
    if instance.is_wl and instance.wl90 is not None:
        entities.extend(
            BeurerAlarmSwitch(coordinator, name, slot)
            for slot in range(len(instance.wl90.alarms))
        )

    async_add_entities(entities)


class BeurerAdaptiveLightingSwitch(
    CoordinatorEntity[BeurerDataUpdateCoordinator], SwitchEntity, RestoreEntity
):
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
        coordinator: BeurerDataUpdateCoordinator,
        name: str,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._entry_id = entry_id
        self._device_name = name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"
        self._is_on: bool = True  # Default: Adaptive Lighting enabled

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"
            LOGGER.debug(
                "Restored Adaptive Lighting state: %s",
                "enabled" if self._is_on else "disabled",
            )

        # Store the switch reference in instance for light entity access
        self._instance.adaptive_lighting_switch = self

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if hasattr(self._instance, "adaptive_lighting_switch"):
            delattr(self._instance, "adaptive_lighting_switch")

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
            "therapy_mode_active": self._instance._therapy_active
            if hasattr(self._instance, "_therapy_active")
            else False,
            "current_effect": self._instance.effect
            if self._instance.effect != "Off"
            else None,
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
        return (
            hasattr(self._instance, "_therapy_active")
            and self._instance._therapy_active
        )


class BeurerDeviceSwitch(CoordinatorEntity[BeurerDataUpdateCoordinator], SwitchEntity):
    """Switch for device hardware settings (feedback sound, fade).

    These control actual device firmware settings discovered from
    APK reverse engineering of the Beurer LightUp app.

    - Feedback Sound: Beep/sound when pressing physical buttons
    - Fade: Smooth brightness transitions instead of instant changes
    """

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        name: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the device switch."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._instance.available

    @property
    def is_on(self) -> bool | None:
        """Return True if the device setting is enabled."""
        if self.entity_description.key == "feedback_sound":
            return self._instance.feedback_enabled
        if self.entity_description.key == "fade":
            return self._instance.fade_enabled
        return None

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
        """Enable the device setting."""
        if self.entity_description.key == "feedback_sound":
            await self._instance.set_feedback(True)
        elif self.entity_description.key == "fade":
            await self._instance.set_fade(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the device setting."""
        if self.entity_description.key == "feedback_sound":
            await self._instance.set_feedback(False)
        elif self.entity_description.key == "fade":
            await self._instance.set_fade(False)


class BeurerAlarmSwitch(CoordinatorEntity[BeurerDataUpdateCoordinator], SwitchEntity):
    """Switch for enabling or disabling an alarm slot on WL75/WL90 lamps."""

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        name: str,
        slot: int,
    ) -> None:
        """Initialize the alarm switch."""
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = name
        self._slot = slot
        self._attr_translation_key = f"alarm_{slot + 1}"
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_alarm_{slot + 1}"

    @property
    def _alarm(self) -> Any:
        """Return the AlarmItem for this slot."""
        if self._instance.wl90 and self._slot < len(self._instance.wl90.alarms):
            return self._instance.wl90.alarms[self._slot]
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available and alarm slot exists."""
        return self._instance.available and self._alarm is not None

    @property
    def is_on(self) -> bool:
        """Return True if the alarm is enabled."""
        alarm = self._alarm
        return bool(alarm.enabled) if alarm else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable this alarm on the device."""
        alarm = self._alarm
        if not alarm or not self._instance.wl90:
            return
        alarm.enabled = True
        await self._instance.wl90.sync_alarm(self._slot, alarm)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable this alarm on the device."""
        alarm = self._alarm
        if not alarm or not self._instance.wl90:
            return
        alarm.enabled = False
        await self._instance.wl90.sync_alarm(self._slot, alarm)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alarm details (time, days, tone, volume, snooze, sunrise)."""
        alarm = self._alarm
        if not alarm:
            return {}
        return {
            "slot": self._slot,
            "time": f"{alarm.hour:02d}:{alarm.minute:02d}",
            "days": alarm.days_list,
            "tone": alarm.tone,
            "volume": alarm.volume,
            "snooze_minutes": alarm.snooze_minutes,
            "sunrise_enabled": alarm.sunrise_enabled,
            "sunrise_time": alarm.sunrise_time,
            "sunrise_brightness": alarm.sunrise_brightness,
        }

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
