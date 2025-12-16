"""The Beurer Daylight Lamps integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
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
        new_device = bluetooth.async_ble_device_from_address(
            hass, mac_address, connectable=True
        )
        if new_device:
            instance.update_ble_device(new_device)

        # Mark device as seen (for availability tracking)
        instance.mark_seen()

    # Register for advertisements from this specific device address
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_device_discovered,
            {"address": mac_address, "connectable": True},
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
        LOGGER.warning(
            "Device %s is no longer seen by any Bluetooth adapter",
            service_info.address,
        )
        instance.mark_unavailable()

    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass,
            _async_device_unavailable,
            mac_address,
            connectable=True,
        )
    )
    LOGGER.debug("Registered unavailability tracker for %s", mac_address)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.disconnect()
    return unload_ok
