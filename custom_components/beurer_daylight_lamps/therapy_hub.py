"""Singleton hub for per-person therapy aggregation across all Beurer lamps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, THERAPY_HUB_IDENTIFIER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

HUB_DATA_KEY = "therapy_hub"


class TherapyHub:
    """Singleton that owns the virtual 'Beurer Therapy Hub' device."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.owning_entry_id: str | None = None

    def ensure_device(self, owning_entry: ConfigEntry) -> dr.DeviceEntry:
        """Create or update the virtual hub device in the device registry.

        Uses async_get_or_create so repeated calls are idempotent — HA
        deduplicates on the identifiers tuple.
        """
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_or_create(
            config_entry_id=owning_entry.entry_id,
            identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)},
            name="Beurer Therapy Hub",
            manufacturer="Beurer",
            model="Therapy Aggregation",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self.owning_entry_id = owning_entry.entry_id
        return device

    def remove_device(self) -> None:
        """Remove the virtual hub device from the device registry.

        Safe to call when the device does not exist (no-op in that case).
        """
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(
            identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)}
        )
        if device is not None:
            dev_reg.async_remove_device(device.id)
        self.owning_entry_id = None


def get_or_create_hub(hass: HomeAssistant) -> TherapyHub:
    """Return the TherapyHub singleton for this hass instance.

    Creates one if it does not yet exist and stores it in
    ``hass.data[DOMAIN][HUB_DATA_KEY]``.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    hub = domain_data.get(HUB_DATA_KEY)
    if hub is None:
        hub = TherapyHub(hass)
        domain_data[HUB_DATA_KEY] = hub
    return hub
