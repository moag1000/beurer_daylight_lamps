"""Repairs for Beurer Daylight Lamps integration.

This module implements repair flows for Gold tier compliance.
Repair flows allow users to fix common issues through a guided UI.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components import bluetooth
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .beurer_daylight_lamps import BeurerInstance
from .const import DOMAIN, LOGGER


class DeviceNotFoundRepairFlow(RepairsFlow):
    """Handler for device not found repair flow."""

    def __init__(self, issue_id: str, data: dict[str, Any]) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self._issue_id = issue_id
        self._data = data
        self._entry_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of the repair flow."""
        # Extract entry_id from issue_id (format: device_not_found_{entry_id})
        self._entry_id = self._issue_id.replace("device_not_found_", "")

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step."""
        if self._entry_id is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            # Try to find and reconnect to the device
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if not entry:
                return self.async_abort(reason="entry_not_found")

            mac: str = entry.data.get(CONF_MAC, "")
            name: str = entry.data.get(CONF_NAME, "Beurer Lamp")

            if not mac:
                return self.async_abort(reason="invalid_config")

            # Check if device is now visible
            ble_device = bluetooth.async_ble_device_from_address(self.hass, mac)
            if not ble_device:
                ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, mac, connectable=False
                )

            if ble_device:
                # Device found! Delete the issue and reload
                ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
                await self.hass.config_entries.async_reload(self._entry_id)
                return self.async_create_entry(data={})

            # Still not found
            return self.async_show_form(
                step_id="confirm",
                errors={"base": "still_not_found"},
                description_placeholders={
                    "name": name,
                    "mac": mac,
                },
            )

        # Get device info for placeholders
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        name = entry.data.get(CONF_NAME, "Beurer Lamp") if entry else "Unknown"
        mac = str(entry.data.get(CONF_MAC, "Unknown")) if entry else "Unknown"

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": name,
                "mac": mac,
            },
        )


class InitializationFailedRepairFlow(RepairsFlow):
    """Handler for initialization failed repair flow."""

    def __init__(self, issue_id: str, data: dict[str, Any]) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self._issue_id = issue_id
        self._data = data
        self._entry_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of the repair flow."""
        # Extract entry_id from issue_id (format: initialization_failed_{entry_id})
        self._entry_id = self._issue_id.replace("initialization_failed_", "")

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step."""
        if self._entry_id is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            # Try to reload the config entry
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if not entry:
                return self.async_abort(reason="entry_not_found")

            # Delete the issue first
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)

            # Try to reload
            try:
                await self.hass.config_entries.async_reload(self._entry_id)
                return self.async_create_entry(data={})
            except Exception as err:
                LOGGER.error("Reload failed: %s", err)
                return self.async_show_form(
                    step_id="confirm",
                    errors={"base": "reload_failed"},
                    description_placeholders=self._data,
                )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=self._data,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow for fixing an issue.

    This is called by Home Assistant when user clicks "Fix" on an issue.
    """
    LOGGER.debug("Creating repair flow for issue: %s", issue_id)

    if issue_id.startswith("device_not_found_"):
        return DeviceNotFoundRepairFlow(issue_id, data or {})
    elif issue_id.startswith("initialization_failed_"):
        return InitializationFailedRepairFlow(issue_id, data or {})

    # Fallback - shouldn't happen
    raise ValueError(f"Unknown issue type: {issue_id}")
