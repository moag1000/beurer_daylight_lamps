"""Custom types for beurer_daylight_lamps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .beurer_daylight_lamps import BeurerInstance
    from .coordinator import BeurerDataUpdateCoordinator


type BeurerConfigEntry = ConfigEntry[BeurerRuntimeData]


@dataclass
class BeurerRuntimeData:
    """Runtime data for Beurer integration.

    This dataclass holds all runtime data for a config entry,
    following the recommended pattern for HA integrations.
    """

    instance: BeurerInstance
    coordinator: BeurerDataUpdateCoordinator
