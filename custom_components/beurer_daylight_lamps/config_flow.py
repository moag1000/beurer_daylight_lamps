"""Config flow for Beurer Daylight Lamps integration."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_MAC
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .beurer_daylight_lamps import discover, get_device, BeurerInstance
from .const import DOMAIN, LOGGER

MANUAL_MAC = "manual"


class BeurerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Beurer Daylight Lamps."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.mac: str | None = None
        self.beurer_instance: BeurerInstance | None = None
        self.name: str | None = None
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the Bluetooth discovery step."""
        LOGGER.debug(
            "Bluetooth discovery: address=%s, name=%s",
            discovery_info.address,
            discovery_info.name,
        )

        # Set unique ID from MAC address
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        # Store discovery info for later steps
        self._discovery_info = discovery_info
        self.mac = discovery_info.address
        self.name = discovery_info.name or f"Beurer {discovery_info.address[-8:]}"

        # Show confirmation dialog to user
        self.context["title_placeholders"] = {"name": self.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Bluetooth discovery."""
        if user_input is not None:
            # User confirmed, optionally update name
            if "name" in user_input and user_input["name"]:
                self.name = user_input["name"]
            return await self.async_step_validate()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default=self.name): str,
                }
            ),
            description_placeholders={"name": self.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step (manual setup)."""
        if user_input is not None:
            if user_input["mac"] == MANUAL_MAC:
                return await self.async_step_manual()

            self.mac = user_input["mac"]
            self.name = user_input["name"]
            await self.async_set_unique_id(format_mac(self.mac))
            self._abort_if_unique_id_configured()
            return await self.async_step_validate()

        already_configured = self._async_current_ids(False)
        devices = await discover()
        devices = [
            device
            for device in devices
            if format_mac(device.address) not in already_configured
        ]

        if not devices:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("mac"): vol.In(
                        {
                            **{device.address: device.name for device in devices},
                            MANUAL_MAC: "Manual MAC entry",
                        }
                    ),
                    vol.Required("name"): str,
                }
            ),
            errors={},
        )

    async def async_step_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate connection by toggling the light."""
        if user_input is not None:
            if "flicker" in user_input:
                if user_input["flicker"]:
                    return self.async_create_entry(
                        title=self.name,
                        data={CONF_MAC: self.mac, "name": self.name},
                    )
                return self.async_abort(reason="cannot_validate")

            if "retry" in user_input and not user_input["retry"]:
                return self.async_abort(reason="cannot_connect")

        error = await self._toggle_light()

        if error:
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "cannot_connect"},
            )

        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema({vol.Required("flicker"): bool}),
            errors={},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual MAC address entry."""
        if user_input is not None:
            self.mac = user_input["mac"]
            self.name = user_input["name"]
            await self.async_set_unique_id(format_mac(self.mac))
            self._abort_if_unique_id_configured()
            return await self.async_step_validate()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("mac"): str,
                    vol.Required("name"): str,
                }
            ),
            errors={},
        )

    async def _toggle_light(self) -> Exception | None:
        """Toggle the light to validate connection."""
        if not self.beurer_instance:
            device = await get_device(self.mac)
            if not device:
                LOGGER.error("Could not find device with MAC %s", self.mac)
                return Exception("Device not found")
            self.beurer_instance = BeurerInstance(device)

        if not self.beurer_instance or not self.beurer_instance._device:
            LOGGER.error(
                "BeurerInstance not properly initialized for MAC %s", self.mac
            )
            return Exception("Instance initialization failed")

        try:
            LOGGER.debug("Going to update from config flow")
            await self.beurer_instance.update()
            LOGGER.debug(
                "Finished updating from config flow, lamp is %s",
                self.beurer_instance.is_on,
            )

            await asyncio.sleep(0.5)

            current_state = bool(self.beurer_instance.is_on)
            if current_state:
                await self.beurer_instance.turn_off()
                await asyncio.sleep(2)
                await self.beurer_instance.turn_on()
            else:
                await self.beurer_instance.turn_on()
                await asyncio.sleep(2)
                await self.beurer_instance.turn_off()

            return None

        except Exception as error:
            LOGGER.error("Error while toggling lamp: %s", str(error))
            return error

        finally:
            try:
                if self.beurer_instance:
                    await self.beurer_instance.disconnect()
            except Exception as error:
                LOGGER.warning("Error during disconnect: %s", str(error))
