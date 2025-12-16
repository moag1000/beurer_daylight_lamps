"""Config flow for Beurer Daylight Lamps integration."""
from __future__ import annotations

import asyncio
from typing import Any

from bleak import BleakError
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.helpers.device_registry import format_mac

from .beurer_daylight_lamps import BeurerInstance, discover, get_device
from .const import DOMAIN, LOGGER

MANUAL_MAC = "manual"


class BeurerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Beurer Daylight Lamps."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._mac: str | None = None
        self._name: str | None = None
        self._instance: BeurerInstance | None = None
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._reauth_entry: ConfigEntry | None = None
        self._reconfigure_entry: ConfigEntry | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        LOGGER.debug(
            "Bluetooth discovery: %s (%s)",
            discovery_info.name,
            discovery_info.address,
        )

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._mac = discovery_info.address
        self._name = discovery_info.name or f"Beurer {discovery_info.address[-8:]}"

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        if user_input is not None:
            if user_input.get(CONF_NAME):
                self._name = user_input[CONF_NAME]
            return await self.async_step_validate()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_NAME, default=self._name): str}
            ),
            description_placeholders={"name": self._name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_MAC] == MANUAL_MAC:
                return await self.async_step_manual()

            self._mac = user_input[CONF_MAC]
            self._name = user_input[CONF_NAME]

            await self.async_set_unique_id(format_mac(self._mac))
            self._abort_if_unique_id_configured()

            return await self.async_step_validate()

        # Discover devices
        configured_macs = self._async_current_ids(include_ignore=False)
        devices = await discover()
        available_devices = [
            d for d in devices if format_mac(d.address) not in configured_macs
        ]

        if not available_devices:
            return await self.async_step_manual()

        device_options = {d.address: d.name or d.address for d in available_devices}
        device_options[MANUAL_MAC] = "Enter MAC manually"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): vol.In(device_options),
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual MAC entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._mac = user_input[CONF_MAC].strip().upper()
            self._name = user_input[CONF_NAME]

            if not self._is_valid_mac(self._mac):
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(format_mac(self._mac))
                self._abort_if_unique_id_configured()
                return await self.async_step_validate()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): str,
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate connection by toggling the light."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("flicker"):
                # Handle reconfigure
                if self._reconfigure_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reconfigure_entry,
                        data={
                            CONF_MAC: self._mac,
                            CONF_NAME: self._name,
                        },
                    )
                    await self.hass.config_entries.async_reload(
                        self._reconfigure_entry.entry_id
                    )
                    return self.async_abort(reason="reconfigure_successful")

                return self.async_create_entry(
                    title=self._name or "Beurer Lamp",
                    data={
                        CONF_MAC: self._mac,
                        CONF_NAME: self._name,
                    },
                )
            if user_input.get("retry") is False:
                return self.async_abort(reason="cannot_connect")

        success = await self._test_connection()

        if not success:
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "cannot_connect"},
            )

        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema({vol.Required("flicker"): bool}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._mac = entry_data.get(CONF_MAC)
        self._name = entry_data.get(CONF_NAME)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            success = await self._test_connection()
            if success:
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={
                            CONF_MAC: self._mac,
                            CONF_NAME: self._name,
                        },
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"name": self._name},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        self._reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reconfigure_entry:
            self._mac = self._reconfigure_entry.data.get(CONF_MAC)
            self._name = self._reconfigure_entry.data.get(CONF_NAME)

        errors: dict[str, str] = {}

        if user_input is not None:
            self._name = user_input[CONF_NAME]
            return await self.async_step_validate()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=self._name): str,
                }
            ),
            errors=errors,
            description_placeholders={"mac": self._mac},
        )

    async def _test_connection(self) -> bool:
        """Test connection by toggling the lamp."""
        try:
            if not self._instance:
                device, rssi = await get_device(self._mac)
                if not device:
                    LOGGER.error("Device not found: %s", self._mac)
                    return False
                self._instance = BeurerInstance(device, rssi)

            LOGGER.debug("Testing connection to %s", self._mac)
            await self._instance.update()
            await asyncio.sleep(0.5)

            is_on = bool(self._instance.is_on)
            if is_on:
                await self._instance.turn_off()
                await asyncio.sleep(1.5)
                await self._instance.turn_on()
            else:
                await self._instance.turn_on()
                await asyncio.sleep(1.5)
                await self._instance.turn_off()

            return True

        except BleakError as err:
            LOGGER.error("BLE error during connection test: %s", err)
            return False
        except (TimeoutError, asyncio.TimeoutError) as err:
            LOGGER.error("Timeout during connection test: %s", err)
            return False
        except OSError as err:
            LOGGER.error("OS error during connection test: %s", err)
            return False
        except ValueError as err:
            LOGGER.error("Invalid device during connection test: %s", err)
            return False

        finally:
            if self._instance:
                try:
                    await self._instance.disconnect()
                except (BleakError, TimeoutError, asyncio.TimeoutError, OSError) as err:
                    LOGGER.debug("Disconnect error: %s", err)
                self._instance = None

    @staticmethod
    def _is_valid_mac(mac: str) -> bool:
        """Validate MAC address format."""
        mac = mac.replace(":", "").replace("-", "")
        if len(mac) != 12:
            return False
        try:
            int(mac, 16)
            return True
        except ValueError:
            return False
