"""The Beurer Daylight Lamps integration."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_entity_ids

from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER
from .coordinator import BeurerDataUpdateCoordinator
from .exceptions import BeurerInitializationError
from .therapy import SunriseProfile

# Service constants
SERVICE_APPLY_PRESET = "apply_preset"
SERVICE_SEND_RAW = "send_raw_command"
SERVICE_SET_TIMER = "set_timer"
SERVICE_START_SUNRISE = "start_sunrise"
SERVICE_START_SUNSET = "start_sunset"
SERVICE_STOP_SIMULATION = "stop_simulation"
ATTR_PRESET = "preset"
ATTR_COMMAND = "command"
ATTR_MINUTES = "minutes"
ATTR_DURATION = "duration"
ATTR_PROFILE = "profile"
ATTR_END_BRIGHTNESS = "end_brightness"

# Preset definitions: {preset_name: (rgb, brightness, color_temp_kelvin, effect)}
# brightness is 0-255, color_temp is Kelvin, effect is effect name or None
PRESETS: dict[str, dict[str, Any]] = {
    "daylight_therapy": {
        "description": "Full brightness daylight for therapy",
        "color_temp_kelvin": 5300,
        "brightness": 255,
    },
    "relax": {
        "description": "Warm, dim light for relaxation",
        "color_temp_kelvin": 2700,
        "brightness": 100,
    },
    "focus": {
        "description": "Cool, bright light for concentration",
        "color_temp_kelvin": 5000,
        "brightness": 230,
    },
    "reading": {
        "description": "Neutral white for comfortable reading",
        "color_temp_kelvin": 4000,
        "brightness": 200,
    },
    "warm_cozy": {
        "description": "Very warm light for cozy atmosphere",
        "color_temp_kelvin": 2700,
        "brightness": 150,
    },
    "cool_bright": {
        "description": "Cool white at full brightness",
        "color_temp_kelvin": 6500,
        "brightness": 255,
    },
    "sunset": {
        "description": "Orange sunset simulation",
        "rgb": (255, 120, 50),
        "brightness": 180,
    },
    "night_light": {
        "description": "Very dim warm light for nighttime",
        "rgb": (255, 100, 50),
        "brightness": 30,
    },
    "energize": {
        "description": "Bright cool light to wake up",
        "color_temp_kelvin": 6000,
        "brightness": 255,
    },
}

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRESET): vol.In(list(PRESETS.keys())),
    }
)

SERVICE_RAW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): cv.string,
    }
)

SERVICE_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
    }
)

# Sunrise profiles available
SUNRISE_PROFILES = ["gentle", "natural", "energize", "therapy"]

SERVICE_SUNRISE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DURATION, default=15): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Optional(ATTR_PROFILE, default="natural"): vol.In(SUNRISE_PROFILES),
    }
)

SERVICE_SUNSET_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DURATION, default=30): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Optional(ATTR_END_BRIGHTNESS, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)

SERVICE_STOP_SIMULATION_SCHEMA = vol.Schema({})

from dataclasses import dataclass


@dataclass
class BeurerRuntimeData:
    """Runtime data for Beurer integration.

    This dataclass holds all runtime data for a config entry,
    following the recommended pattern for HA integrations.
    """

    instance: BeurerInstance
    coordinator: BeurerDataUpdateCoordinator


if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance as BeurerInstanceType
    # Type alias only evaluated during type checking
    BeurerConfigEntry = ConfigEntry[BeurerRuntimeData]
else:
    BeurerConfigEntry = ConfigEntry

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Set up Beurer daylight lamp from a config entry."""
    mac_address = entry.data[CONF_MAC]
    device_name = entry.data.get(CONF_NAME, "Beurer Lamp")
    LOGGER.debug("Setting up Beurer device with MAC: %s", mac_address)

    # Use Home Assistant's Bluetooth stack - this automatically uses all adapters
    # including ESPHome Bluetooth Proxies for better range and reliability
    # Try both connectable and non-connectable devices
    ble_device = bluetooth.async_ble_device_from_address(
        hass, mac_address
    )
    # If not found, explicitly try non-connectable
    if not ble_device:
        ble_device = bluetooth.async_ble_device_from_address(
            hass, mac_address, connectable=False
        )

    # Also get the latest service info for RSSI (try both types)
    service_info = bluetooth.async_last_service_info(
        hass, mac_address
    )
    if not service_info:
        service_info = bluetooth.async_last_service_info(
            hass, mac_address, connectable=False
        )
    rssi = service_info.rssi if service_info else None

    device_initially_available = ble_device is not None

    if ble_device is None:
        LOGGER.debug(
            "Device %s not currently visible via Bluetooth - will retry when seen",
            mac_address,
        )
        # Create a dummy BLEDevice for now - passive listening will update it
        from bleak.backends.device import BLEDevice
        ble_device = BLEDevice(
            address=mac_address,
            name=device_name,
            details={},  # Empty details for placeholder
        )
        LOGGER.info(
            "Created placeholder device for %s - waiting for Bluetooth advertisement",
            mac_address,
        )
    else:
        LOGGER.info(
            "Found device %s via HA Bluetooth stack (RSSI: %s)",
            mac_address,
            rssi,
        )

    LOGGER.debug(
        "Device %s initial availability: %s",
        mac_address,
        rssi,
    )

    # Clear any previous connection issues if we found the device
    ir.async_delete_issue(hass, DOMAIN, f"device_not_found_{entry.entry_id}")

    try:
        instance = BeurerInstance(ble_device, rssi, hass)
        # Set initial BLE availability based on whether device was found
        if not device_initially_available:
            instance._ble_available = False
            LOGGER.info("Device %s marked as initially unavailable", mac_address)
    except ValueError as err:
        LOGGER.error("Failed to create BeurerInstance for %s: %s", mac_address, err)
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"initialization_failed_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="initialization_failed",
            translation_placeholders={
                "name": device_name,
                "mac": mac_address,
                "error": str(err),
            },
        )
        raise ConfigEntryNotReady(f"Failed to initialize {mac_address}") from err

    # Clear any previous initialization issues
    ir.async_delete_issue(hass, DOMAIN, f"initialization_failed_{entry.entry_id}")

    # Create coordinator for centralized data management
    coordinator = BeurerDataUpdateCoordinator(hass, instance, device_name)

    # Store both instance and coordinator in runtime_data
    entry.runtime_data = BeurerRuntimeData(instance=instance, coordinator=coordinator)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Register callback for real-time Bluetooth updates (RSSI, device presence)
    # This enables passive listening - we get notified when the device advertises
    @callback
    def _async_device_discovered(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle Bluetooth advertisement from the device."""
        LOGGER.debug(
            "BLE advertisement from %s: RSSI=%s, change=%s, source=%s",
            service_info.address,
            service_info.rssi,
            change,
            service_info.source,
        )
        # Update RSSI from advertisement
        if service_info.rssi:
            instance.update_rssi(service_info.rssi)

        # Update the BLE device reference to use the best available adapter
        # Try both connectable and non-connectable devices
        new_device = bluetooth.async_ble_device_from_address(
            hass, mac_address
        )
        if not new_device:
            new_device = bluetooth.async_ble_device_from_address(
                hass, mac_address, connectable=False
            )
        if new_device:
            instance.update_ble_device(new_device)

        # Mark device as seen (for availability tracking)
        instance.mark_seen()

    # Register for advertisements from this specific device address
    # Don't filter by connectable - some devices alternate between
    # connectable and non-connectable advertisement packets
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_device_discovered,
            {"address": mac_address},
            BluetoothScanningMode.PASSIVE,
        )
    )
    LOGGER.debug("Registered Bluetooth callback for %s (passive scanning)", mac_address)

    # Track when device becomes unavailable (not seen for ~5 minutes)
    @callback
    def _async_device_unavailable(
        service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Handle device becoming unavailable."""
        LOGGER.debug(
            "Device %s is no longer seen by any Bluetooth adapter",
            service_info.address,
        )
        instance.mark_unavailable()

    # Don't filter by connectable - some devices alternate between
    # connectable and non-connectable advertisement packets
    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass,
            _async_device_unavailable,
            mac_address,
        )
    )
    LOGGER.debug("Registered unavailability tracker for %s", mac_address)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once)
    await _async_setup_services(hass)

    # Auto-connect after setup to get initial state
    # This runs in the background to not block the setup
    async def _async_initial_connect() -> None:
        """Try to connect and get initial state."""
        await asyncio.sleep(2)  # Give BLE stack time to settle
        if device_initially_available:
            LOGGER.debug("Attempting initial connection to %s", mac_address)
            try:
                connected = await instance.connect()
                if connected:
                    LOGGER.info("Initial connection to %s successful", mac_address)
                else:
                    LOGGER.debug("Initial connection to %s failed, will retry on demand", mac_address)
            except Exception as err:
                LOGGER.debug("Initial connection to %s failed: %s", mac_address, err)

    # Use async_create_background_task for proper task tracking and error handling
    entry.async_create_background_task(
        hass,
        _async_initial_connect(),
        f"beurer_initial_connect_{mac_address}",
    )

    return True


async def _async_get_instances_from_target(
    hass: HomeAssistant, call: ServiceCall, service_name: str = ""
) -> list[BeurerInstance]:
    """Get BeurerInstance objects from service call target.

    Supports targeting by entity_id, device_id, or area_id through the
    standard Home Assistant target selector.

    Args:
        hass: Home Assistant instance
        call: Service call with target information
        service_name: Name of service for logging (optional)

    Returns:
        List of BeurerInstance objects for targeted entities
    """
    log_prefix = f"{service_name}: " if service_name else ""
    instances: list[BeurerInstance] = []

    # Extract entity IDs from target (handles entity_id, device_id, area_id)
    entity_ids = await async_extract_entity_ids(hass, call)

    if not entity_ids:
        LOGGER.warning("%sNo target entities specified", log_prefix)
        return instances

    entity_reg = er.async_get(hass)
    seen_config_entries: set[str] = set()

    for entity_id in entity_ids:
        # Only process light entities from our integration
        if not entity_id.startswith("light."):
            continue

        entity_entry = entity_reg.async_get(entity_id)
        if not entity_entry:
            LOGGER.debug("%sEntity %s not found in registry", log_prefix, entity_id)
            continue

        if entity_entry.platform != DOMAIN:
            LOGGER.debug(
                "%sEntity %s is not a Beurer entity (platform: %s)",
                log_prefix, entity_id, entity_entry.platform
            )
            continue

        # Avoid duplicate instances when multiple entities target same device
        config_entry_id = entity_entry.config_entry_id
        if config_entry_id in seen_config_entries:
            continue
        seen_config_entries.add(config_entry_id)

        entry = hass.config_entries.async_get_entry(config_entry_id)
        if entry and hasattr(entry, "runtime_data") and entry.runtime_data:
            instances.append(entry.runtime_data.instance)
        else:
            LOGGER.warning(
                "%sConfig entry not ready for entity %s", log_prefix, entity_id
            )

    if not instances:
        LOGGER.warning("%sNo valid Beurer instances found for target", log_prefix)

    return instances


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up Beurer services."""
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_PRESET):
        return  # Already registered

    async def async_apply_preset(call: ServiceCall) -> None:
        """Apply a preset to a Beurer lamp."""
        preset_name = call.data[ATTR_PRESET]

        instances = await _async_get_instances_from_target(hass, call, "PRESET")
        if not instances:
            return

        preset = PRESETS[preset_name]

        # Apply preset settings
        from homeassistant.util.color import color_temperature_to_rgb

        for instance in instances:
            LOGGER.debug("Applying preset '%s' to %s", preset_name, instance.mac)

            if "rgb" in preset:
                await instance.set_color(preset["rgb"])
            elif "color_temp_kelvin" in preset:
                rgb = color_temperature_to_rgb(preset["color_temp_kelvin"])
                await instance.set_color(rgb)

            if "brightness" in preset:
                await instance.set_color_brightness(preset["brightness"])

            LOGGER.info("Applied preset '%s' to %s", preset_name, instance.mac)

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PRESET,
        async_apply_preset,
        schema=SERVICE_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_APPLY_PRESET)

    async def async_send_raw_command(call: ServiceCall) -> None:
        """Send a raw BLE command to a Beurer lamp (Expert mode)."""
        command_str = call.data[ATTR_COMMAND]

        instances = await _async_get_instances_from_target(hass, call, "RAW_CMD")
        if not instances:
            return

        # Parse hex bytes from command string (e.g., "33 01 1E" or "33011E")
        try:
            hex_str = command_str.replace(" ", "").replace("0x", "")
            payload = [int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2)]
        except ValueError as err:
            LOGGER.error("RAW_CMD: Invalid hex command '%s': %s", command_str, err)
            return

        LOGGER.debug("RAW_CMD: Parsed payload: %s", [f"0x{b:02X}" for b in payload])

        for instance in instances:
            success = await instance._send_packet(payload)
            if success:
                LOGGER.debug("RAW_CMD: Sent successfully to %s", instance.mac)
            else:
                LOGGER.error("RAW_CMD: Failed to send to %s", instance.mac)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_RAW,
        async_send_raw_command,
        schema=SERVICE_RAW_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_SEND_RAW)

    async def async_set_timer(call: ServiceCall) -> None:
        """Set a timer on a Beurer lamp (requires RGB mode).

        Timer will turn off the lamp after the specified minutes.
        Note: Timer only works when the lamp is in RGB mode.
        """
        minutes = call.data[ATTR_MINUTES]

        instances = await _async_get_instances_from_target(hass, call, "TIMER")
        if not instances:
            return

        for instance in instances:
            LOGGER.debug("TIMER: Setting %d minute timer on %s", minutes, instance.mac)
            success = await instance.set_timer(minutes)
            if success:
                LOGGER.debug("TIMER: Set %d minute timer on %s", minutes, instance.mac)
            else:
                LOGGER.error("TIMER: Failed to set timer on %s", instance.mac)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TIMER,
        async_set_timer,
        schema=SERVICE_TIMER_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_SET_TIMER)

    # Sunrise/Sunset simulation services
    async def async_start_sunrise(call: ServiceCall) -> None:
        """Start a sunrise simulation on a Beurer lamp.

        Gradually increases brightness and color temperature to simulate
        natural sunrise. This is a lifestyle feature, not a medical device.
        """
        duration = call.data.get(ATTR_DURATION, 15)
        profile_name = call.data.get(ATTR_PROFILE, "natural")

        instances = await _async_get_instances_from_target(hass, call, "SUNRISE")
        if not instances:
            return

        # Convert profile name to enum
        try:
            profile = SunriseProfile(profile_name)
        except ValueError:
            LOGGER.error("SUNRISE: Unknown profile '%s'", profile_name)
            return

        for instance in instances:
            LOGGER.info(
                "SUNRISE: Starting %d min %s sunrise on %s",
                duration, profile_name, instance.mac
            )
            await instance.sunrise_simulation.start_sunrise(duration, profile)
            LOGGER.info("SUNRISE: Started on %s", instance.mac)

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SUNRISE,
        async_start_sunrise,
        schema=SERVICE_SUNRISE_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_START_SUNRISE)

    async def async_start_sunset(call: ServiceCall) -> None:
        """Start a sunset simulation on a Beurer lamp.

        Gradually decreases brightness and shifts to warm light to simulate
        natural sunset. This is a lifestyle feature, not a medical device.
        """
        duration = call.data.get(ATTR_DURATION, 30)
        end_brightness = call.data.get(ATTR_END_BRIGHTNESS, 0)

        instances = await _async_get_instances_from_target(hass, call, "SUNSET")
        if not instances:
            return

        for instance in instances:
            LOGGER.info(
                "SUNSET: Starting %d min sunset (end: %d%%) on %s",
                duration, end_brightness, instance.mac
            )
            await instance.sunrise_simulation.start_sunset(duration, end_brightness)
            LOGGER.info("SUNSET: Started on %s", instance.mac)

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SUNSET,
        async_start_sunset,
        schema=SERVICE_SUNSET_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_START_SUNSET)

    async def async_stop_simulation(call: ServiceCall) -> None:
        """Stop any running sunrise/sunset simulation."""
        instances = await _async_get_instances_from_target(hass, call, "STOP_SIM")
        if not instances:
            return

        for instance in instances:
            LOGGER.debug("STOP_SIM: Stopping simulation on %s", instance.mac)
            await instance.sunrise_simulation.stop()
            LOGGER.info("STOP_SIM: Simulation stopped on %s", instance.mac)

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_SIMULATION,
        async_stop_simulation,
        schema=SERVICE_STOP_SIMULATION_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_STOP_SIMULATION)


async def async_unload_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Shutdown coordinator first
        await entry.runtime_data.coordinator.async_shutdown()
        # Then disconnect the BLE instance
        await entry.runtime_data.instance.disconnect()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: BeurerConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a device from the config entry.

    This allows users to manually remove stale devices from the device registry.
    For single-device integrations like this one, the device is tied to the
    config entry, so we allow removal which effectively orphans the device
    until the config entry is also removed.

    Returns True to allow device removal, False to prevent it.
    """
    # For this integration, each config entry has exactly one device
    # We allow removal - the user can re-add via reconfiguration if needed
    LOGGER.info(
        "Allowing removal of device %s from config entry %s",
        device_entry.id,
        config_entry.entry_id,
    )
    return True
