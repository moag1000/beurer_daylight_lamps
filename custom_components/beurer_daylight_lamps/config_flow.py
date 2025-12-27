"""Config flow for Beurer Daylight Lamps integration."""
from __future__ import annotations

import asyncio
from typing import Any

from bleak import BleakError
from bleak.backends.device import BLEDevice
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import callback

# Option constants
CONF_THERAPY_GOAL = "therapy_goal"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ADAPTIVE_LIGHTING_DEFAULT = "adaptive_lighting_default"

DEFAULT_THERAPY_GOAL = 30
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_ADAPTIVE_LIGHTING = True
from homeassistant.helpers.device_registry import format_mac

from .beurer_daylight_lamps import BeurerInstance
from .const import DEVICE_NAME_PREFIXES, DOMAIN, LOGGER

MANUAL_MAC = "manual"


class BeurerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Beurer Daylight Lamps."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return BeurerOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._mac: str | None = None
        self._name: str | None = None
        self._instance: BeurerInstance | None = None
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._ble_device: BLEDevice | None = None
        self._rssi: int | None = None
        self._reauth_entry: ConfigEntry | None = None
        self._reconfigure_entry: ConfigEntry | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        LOGGER.debug(
            "Bluetooth discovery: %s (%s) RSSI: %s",
            discovery_info.name,
            discovery_info.address,
            discovery_info.rssi,
        )

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._mac = discovery_info.address
        self._name = discovery_info.name or f"Beurer {discovery_info.address[-8:]}"
        self._ble_device = discovery_info.device
        self._rssi = discovery_info.rssi

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

            # Use cached device info if available
            if self._mac in self._discovered_devices:
                info = self._discovered_devices[self._mac]
                self._ble_device = info.device
                self._rssi = info.rssi
                LOGGER.debug(
                    "Using cached device: %s (RSSI: %s)",
                    self._mac,
                    self._rssi,
                )

            await self.async_set_unique_id(format_mac(self._mac))
            self._abort_if_unique_id_configured()

            return await self.async_step_validate()

        # Use Home Assistant's Bluetooth stack instead of custom BLE scan
        # This is more efficient as HA already continuously scans for devices
        configured_macs = self._async_current_ids(include_ignore=False)

        # Get both connectable and non-connectable devices
        # IMPORTANT: We prefer connectable devices as they can actually be connected
        discovered_connectable = async_discovered_service_info(self.hass, connectable=True)
        discovered_non_connectable = async_discovered_service_info(self.hass, connectable=False)

        # Track which devices are connectable
        connectable_addresses = {info.address for info in discovered_connectable}

        # Combine both lists (use dict to deduplicate by address)
        # PREFER connectable version if both exist
        all_discovered = {}
        for info in discovered_connectable:
            all_discovered[info.address] = (info, True)  # (info, is_connectable)
        for info in discovered_non_connectable:
            if info.address not in all_discovered:
                all_discovered[info.address] = (info, False)

        LOGGER.debug(
            "Found %d connectable and %d non-connectable devices, %d total unique",
            len(discovered_connectable),
            len(discovered_non_connectable),
            len(all_discovered),
        )

        # Filter for Beurer TL devices by name prefix and cache them
        self._discovered_devices = {}
        self._device_connectable = {}  # Track if device is connectable
        for addr, (info, is_connectable) in all_discovered.items():
            if (
                info.name
                and info.name.lower().startswith(DEVICE_NAME_PREFIXES)
                and format_mac(info.address) not in configured_macs
            ):
                LOGGER.debug(
                    "Found Beurer device: %s (%s) RSSI: %s, connectable: %s",
                    info.name,
                    info.address,
                    info.rssi,
                    is_connectable,
                )
                self._discovered_devices[info.address] = info
                self._device_connectable[info.address] = is_connectable

        if not self._discovered_devices:
            return await self.async_step_manual()

        # Build options with name, RSSI info, and connectable status
        device_options = {}
        for addr, info in self._discovered_devices.items():
            is_conn = self._device_connectable.get(addr, True)
            name = info.name or addr
            rssi_str = f" ({info.rssi} dBm)" if info.rssi else ""
            # Note: Even "non-connectable" devices may work via ESPHome proxy
            if not is_conn:
                device_options[addr] = f"{name}{rssi_str} (via Proxy)"
            else:
                device_options[addr] = f"{name}{rssi_str}"
        device_options[MANUAL_MAC] = "MAC manuell eingeben"

        # Get first device name as default
        first_device = next(iter(self._discovered_devices.values()), None)
        default_name = first_device.name if first_device else ""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): vol.In(device_options),
                    vol.Required(CONF_NAME, default=default_name): str,
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
                # Use cached BLE device if available (faster, no scan needed)
                if self._ble_device:
                    LOGGER.debug(
                        "Using cached BLE device for %s (RSSI: %s)",
                        self._mac,
                        self._rssi,
                    )
                    self._instance = BeurerInstance(
                        self._ble_device, self._rssi, self.hass
                    )
                else:
                    # Use HA Bluetooth stack to find device (includes all proxies)
                    # Try both connectable and non-connectable devices
                    LOGGER.debug(
                        "Getting device %s via HA Bluetooth stack...", self._mac
                    )

                    # Try to get a CONNECTABLE device first (required for connection)
                    ble_device = bluetooth.async_ble_device_from_address(
                        self.hass, self._mac, connectable=True
                    )

                    # If not found as connectable, check if visible as non-connectable
                    if not ble_device:
                        non_conn = bluetooth.async_ble_device_from_address(
                            self.hass, self._mac, connectable=False
                        )
                        if non_conn:
                            LOGGER.warning(
                                "Device %s found but NOT connectable - "
                                "may be in sleep mode or out of range",
                                self._mac,
                            )
                            # Use it anyway, connection will fail with clear error
                            ble_device = non_conn

                    if not ble_device:
                        LOGGER.error(
                            "Device %s not found via any Bluetooth adapter", self._mac
                        )
                        return False

                    # Get RSSI from service info (try both types)
                    service_info = bluetooth.async_last_service_info(
                        self.hass, self._mac
                    )
                    if not service_info:
                        service_info = bluetooth.async_last_service_info(
                            self.hass, self._mac, connectable=False
                        )
                    rssi = service_info.rssi if service_info else None

                    self._ble_device = ble_device
                    self._rssi = rssi
                    self._instance = BeurerInstance(ble_device, rssi, self.hass)

            LOGGER.debug("Testing connection to %s", self._mac)
            # Add timeout - ESPHome proxies can connect even to "non-connectable" devices
            # but we need a reasonable timeout to prevent hanging forever
            try:
                async with asyncio.timeout(45):  # 45 second timeout (proxies may be slow)
                    await self._instance.update()
            except asyncio.TimeoutError:
                LOGGER.error(
                    "Connection test timed out for %s after 45s. "
                    "If using ESPHome Bluetooth Proxy, ensure the proxy is online and in range.",
                    self._mac,
                )
                return False
            await asyncio.sleep(0.5)

            # Toggle lamp to confirm it works
            is_on = bool(self._instance.is_on)
            LOGGER.debug("Device %s is currently %s", self._mac, "on" if is_on else "off")

            if is_on:
                await self._instance.turn_off()
                await asyncio.sleep(1.5)
                await self._instance.turn_on()
            else:
                await self._instance.turn_on()
                await asyncio.sleep(1.5)
                await self._instance.turn_off()

            LOGGER.info("Connection test successful for %s", self._mac)
            return True

        except BleakError as err:
            LOGGER.error("BLE error during connection test for %s: %s", self._mac, err)
            return False
        except (TimeoutError, asyncio.TimeoutError) as err:
            LOGGER.error("Timeout during connection test for %s: %s", self._mac, err)
            return False
        except OSError as err:
            LOGGER.error("OS error during connection test for %s: %s", self._mac, err)
            return False
        except ValueError as err:
            LOGGER.error("Invalid device during connection test for %s: %s", self._mac, err)
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


class BeurerOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Beurer Daylight Lamps."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update options
            return self.async_create_entry(title="", data=user_input)

        # Get current options with defaults
        current_options = self._config_entry.options
        therapy_goal = current_options.get(CONF_THERAPY_GOAL, DEFAULT_THERAPY_GOAL)
        update_interval = current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        adaptive_lighting = current_options.get(
            CONF_ADAPTIVE_LIGHTING_DEFAULT, DEFAULT_ADAPTIVE_LIGHTING
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_THERAPY_GOAL,
                        default=therapy_goal,
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=update_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                    vol.Optional(
                        CONF_ADAPTIVE_LIGHTING_DEFAULT,
                        default=adaptive_lighting,
                    ): bool,
                }
            ),
        )
