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
from homeassistant.helpers import device_registry as dr, issue_registry as ir
import homeassistant.helpers.config_validation as cv

from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER
from .therapy import SunriseProfile

# Service constants
SERVICE_APPLY_PRESET = "apply_preset"
SERVICE_SEND_RAW = "send_raw_command"
SERVICE_SET_TIMER = "set_timer"
SERVICE_START_SUNRISE = "start_sunrise"
SERVICE_START_SUNSET = "start_sunset"
SERVICE_STOP_SIMULATION = "stop_simulation"
ATTR_DEVICE_ID = "device_id"
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
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PRESET): vol.In(list(PRESETS.keys())),
    }
)

SERVICE_RAW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_COMMAND): cv.string,
    }
)

SERVICE_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
    }
)

# Sunrise profiles available
SUNRISE_PROFILES = ["gentle", "natural", "energize", "therapy"]

SERVICE_SUNRISE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_DURATION, default=15): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Optional(ATTR_PROFILE, default="natural"): vol.In(SUNRISE_PROFILES),
    }
)

SERVICE_SUNSET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_DURATION, default=30): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        vol.Optional(ATTR_END_BRIGHTNESS, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)

SERVICE_STOP_SIMULATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance as BeurerInstanceType
    # Type alias only evaluated during type checking
    BeurerConfigEntry = ConfigEntry[BeurerInstance]
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

    entry.runtime_data = instance

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

    hass.async_create_task(_async_initial_connect())

    return True


def _get_instance_for_device(
    hass: HomeAssistant, device_id: str, service_name: str = ""
) -> BeurerInstance | None:
    """Get BeurerInstance for a device ID.

    Args:
        hass: Home Assistant instance
        device_id: Device ID from service call
        service_name: Name of service for logging (optional)

    Returns:
        BeurerInstance if found, None otherwise
    """
    log_prefix = f"{service_name}: " if service_name else ""

    device_reg = dr.async_get(hass)
    device = device_reg.async_get(device_id)

    if not device:
        LOGGER.error("%sDevice %s not found", log_prefix, device_id)
        return None

    # Find config entry for this device
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            if hasattr(entry, "runtime_data"):
                return entry.runtime_data
            LOGGER.error("%sConfig entry not ready for device %s", log_prefix, device_id)
            return None

    LOGGER.error("%sNo Beurer config entry found for device %s", log_prefix, device_id)
    return None


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up Beurer services."""
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_PRESET):
        return  # Already registered

    async def async_apply_preset(call: ServiceCall) -> None:
        """Apply a preset to a Beurer lamp."""
        device_id = call.data[ATTR_DEVICE_ID]
        preset_name = call.data[ATTR_PRESET]

        LOGGER.debug("Applying preset '%s' to device %s", preset_name, device_id)

        instance = _get_instance_for_device(hass, device_id, "PRESET")
        if not instance:
            return
        preset = PRESETS[preset_name]

        # Apply preset settings
        from homeassistant.util.color import color_temperature_to_rgb

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
        device_id = call.data[ATTR_DEVICE_ID]
        command_str = call.data[ATTR_COMMAND]

        LOGGER.debug("RAW_CMD: Sending '%s' to device %s", command_str, device_id)

        instance = _get_instance_for_device(hass, device_id, "RAW_CMD")
        if not instance:
            return

        # Parse hex bytes from command string (e.g., "33 01 1E" or "33011E")
        try:
            hex_str = command_str.replace(" ", "").replace("0x", "")
            payload = [int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2)]
        except ValueError as err:
            LOGGER.error("RAW_CMD: Invalid hex command '%s': %s", command_str, err)
            return

        LOGGER.debug("RAW_CMD: Parsed payload: %s", [f"0x{b:02X}" for b in payload])

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
        device_id = call.data[ATTR_DEVICE_ID]
        minutes = call.data[ATTR_MINUTES]

        LOGGER.debug("TIMER: Setting %d minute timer on device %s", minutes, device_id)

        instance = _get_instance_for_device(hass, device_id, "TIMER")
        if not instance:
            return

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
        device_id = call.data[ATTR_DEVICE_ID]
        duration = call.data.get(ATTR_DURATION, 15)
        profile_name = call.data.get(ATTR_PROFILE, "natural")

        LOGGER.info(
            "SUNRISE: Starting %d min %s sunrise on device %s",
            duration, profile_name, device_id
        )

        instance = _get_instance_for_device(hass, device_id, "SUNRISE")
        if not instance:
            return

        # Convert profile name to enum
        try:
            profile = SunriseProfile(profile_name)
        except ValueError:
            LOGGER.error("SUNRISE: Unknown profile '%s'", profile_name)
            return

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
        device_id = call.data[ATTR_DEVICE_ID]
        duration = call.data.get(ATTR_DURATION, 30)
        end_brightness = call.data.get(ATTR_END_BRIGHTNESS, 0)

        LOGGER.info(
            "SUNSET: Starting %d min sunset (end: %d%%) on device %s",
            duration, end_brightness, device_id
        )

        instance = _get_instance_for_device(hass, device_id, "SUNSET")
        if not instance:
            return

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
        device_id = call.data[ATTR_DEVICE_ID]

        LOGGER.debug("STOP_SIM: Stopping simulation on device %s", device_id)

        instance = _get_instance_for_device(hass, device_id, "STOP_SIM")
        if not instance:
            return

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
        await entry.runtime_data.disconnect()
    return unload_ok
