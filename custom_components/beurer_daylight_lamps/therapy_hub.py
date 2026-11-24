"""Singleton hub for per-person therapy aggregation across all Beurer lamps."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, THERAPY_HUB_IDENTIFIER
from .therapy import start_of_local_week

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .therapy import TherapyTracker

HUB_DATA_KEY = "therapy_hub"


class TherapyHub:
    """Singleton that owns the virtual 'Beurer Therapy Hub' device."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize TherapyHub."""
        self.hass = hass
        self.owning_entry_id: str | None = None

    def ensure_device(self, owning_entry: ConfigEntry) -> dr.DeviceEntry | None:
        """Create or update the virtual hub device in the device registry.

        Uses async_get_or_create so repeated calls are idempotent — HA
        deduplicates on the identifiers tuple.

        Returns None when the config entry is not registered with HA (e.g. in
        test mocks that use a bare MagicMock entry), so callers must handle a
        None return value gracefully.
        """
        dev_reg = dr.async_get(self.hass)
        try:
            device = dev_reg.async_get_or_create(
                config_entry_id=owning_entry.entry_id,
                identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)},
                name="Beurer Therapy Hub",
                manufacturer="Beurer",
                model="Therapy Aggregation",
                entry_type=dr.DeviceEntryType.SERVICE,
            )
        except HomeAssistantError as err:
            LOGGER.debug("Could not create therapy hub device: %s", err)
            return None
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
    return cast("TherapyHub", hub)


# ---------------------------------------------------------------------------
# Per-person aggregation helpers
# ---------------------------------------------------------------------------


def _iter_trackers(hass: HomeAssistant) -> Iterator[TherapyTracker]:
    """Yield each lamp's TherapyTracker from runtime_data."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        instance = getattr(runtime, "instance", None)
        if instance is None:
            continue
        tracker = getattr(instance, "therapy_tracker", None)
        if tracker is not None:
            yield tracker


def today_minutes_for(hass: HomeAssistant, person_id: str) -> float:
    """Return total therapy minutes for person_id today (local calendar day)."""
    since = dt_util.start_of_local_day()
    return sum(t.minutes_since(since, person_id) for t in _iter_trackers(hass))


def week_minutes_for(hass: HomeAssistant, person_id: str) -> float:
    """Return total therapy minutes for person_id this week (Monday, local time)."""
    since = start_of_local_week()
    return sum(t.minutes_since(since, person_id) for t in _iter_trackers(hass))


def goal_progress_for(hass: HomeAssistant, person_id: str, goal_minutes: int) -> int:
    """Return today's goal completion for person_id as an integer percentage (0-100)."""
    if goal_minutes <= 0:
        return 0
    return min(100, int(today_minutes_for(hass, person_id) / goal_minutes * 100))
