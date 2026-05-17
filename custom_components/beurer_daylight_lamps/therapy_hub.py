"""Singleton hub for per-person therapy aggregation across all Beurer lamps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER, THERAPY_HUB_IDENTIFIER

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


def _sum_minutes_for(hass: HomeAssistant, person_id: str, since: datetime) -> float:
    total = 0.0
    for tracker in _iter_trackers(hass):
        for session in tracker.sessions:
            if (
                session.person_id == person_id
                and session.is_therapy_light
                and session.start_time >= since
            ):
                total += session.duration_minutes
        cur = tracker._current_session
        if (
            cur is not None
            and cur.person_id == person_id
            and cur.is_therapy_light
            and cur.start_time >= since
        ):
            total += cur.duration_minutes
    return total


def today_minutes_for(hass: HomeAssistant, person_id: str) -> float:
    """Return total therapy minutes for person_id today (UTC midnight cutoff)."""
    midnight = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return _sum_minutes_for(hass, person_id, midnight)


def week_minutes_for(hass: HomeAssistant, person_id: str) -> float:
    """Return total therapy minutes for person_id this week (Mon 00:00 UTC cutoff)."""
    now = datetime.now(tz=UTC)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return _sum_minutes_for(hass, person_id, week_start)


def goal_progress_for(hass: HomeAssistant, person_id: str, goal_minutes: int) -> int:
    """Return today's goal completion for person_id as an integer percentage (0-100)."""
    if goal_minutes <= 0:
        return 0
    return min(100, int(today_minutes_for(hass, person_id) / goal_minutes * 100))
