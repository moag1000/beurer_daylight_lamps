"""The Beurer Daylight Lamps integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .beurer_daylight_lamps import BeurerInstance, get_device
from .const import DOMAIN, LOGGER

PLATFORMS: list[Platform] = [Platform.LIGHT]

type BeurerConfigEntry = ConfigEntry[BeurerInstance]


async def async_setup_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Set up Beurer daylight lamp from a config entry."""
    mac_address = entry.data[CONF_MAC]
    LOGGER.debug("Setting up Beurer device with MAC: %s", mac_address)

    device = await get_device(mac_address)
    if device is None:
        LOGGER.error("Could not find device with MAC %s", mac_address)
        raise ConfigEntryNotReady(f"Could not find Beurer device {mac_address}")

    try:
        instance = BeurerInstance(device)
    except ValueError as err:
        LOGGER.error("Failed to create BeurerInstance for %s: %s", mac_address, err)
        raise ConfigEntryNotReady(f"Failed to initialize {mac_address}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = instance
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeurerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        instance: BeurerInstance = hass.data[DOMAIN].pop(entry.entry_id)
        await instance.disconnect()
    return unload_ok
