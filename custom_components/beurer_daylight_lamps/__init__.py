"""The Beurer Daylight Lamps integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from .beurer_daylight_lamps import BeurerInstance as BeurerInstanceType
    # Type alias only evaluated during type checking
    BeurerConfigEntry = ConfigEntry[BeurerInstance]
else:
    BeurerConfigEntry = ConfigEntry

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Set up Beurer daylight lamp from a config entry."""
    mac_address = entry.data[CONF_MAC]
    device_name = entry.data.get(CONF_NAME, "Beurer Lamp")
    LOGGER.debug("Setting up Beurer device with MAC: %s", mac_address)

    # Use Home Assistant's Bluetooth stack - this automatically uses all adapters
    # including ESPHome Bluetooth Proxies for better range and reliability
    ble_device = bluetooth.async_ble_device_from_address(
        hass, mac_address, connectable=True
    )

    # Also get the latest service info for RSSI
    service_info = bluetooth.async_last_service_info(
        hass, mac_address, connectable=True
    )
    rssi = service_info.rssi if service_info else None

    if ble_device is None:
        LOGGER.error(
            "Could not find device %s via any Bluetooth adapter (including proxies)",
            mac_address,
        )
        # Create repair issue for connection problem
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"device_not_found_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="device_not_found",
            translation_placeholders={
                "name": device_name,
                "mac": mac_address,
            },
        )
        raise ConfigEntryNotReady(f"Could not find Beurer device {mac_address}")

    LOGGER.info(
        "Found device %s via HA Bluetooth stack (RSSI: %s)",
        mac_address,
        rssi,
    )

    # Clear any previous connection issues if we found the device
    ir.async_delete_issue(hass, DOMAIN, f"device_not_found_{entry.entry_id}")

    try:
        instance = BeurerInstance(ble_device, rssi, hass)
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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.disconnect()
    return unload_ok
