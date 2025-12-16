"""Test the Beurer Daylight Lamps config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.beurer_daylight_lamps.const import DOMAIN


async def test_form_no_devices(hass: HomeAssistant) -> None:
    """Test we show manual form when no devices found."""
    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.discover",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_form_with_devices(hass: HomeAssistant) -> None:
    """Test we show device selection when devices found."""
    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"
    mock_device.name = "TL100"

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.discover",
        return_value=[mock_device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_manual_invalid_mac(hass: HomeAssistant) -> None:
    """Test invalid MAC address in manual entry."""
    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.discover",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "invalid", CONF_NAME: "Test"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_MAC: "invalid_mac"}


async def test_manual_valid_mac(hass: HomeAssistant) -> None:
    """Test valid MAC address proceeds to validation."""
    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"
    mock_device.name = "TL100"

    mock_instance = MagicMock()
    mock_instance.is_on = False
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock()

    with (
        patch(
            "custom_components.beurer_daylight_lamps.config_flow.discover",
            return_value=[],
        ),
        patch(
            "custom_components.beurer_daylight_lamps.config_flow.get_device",
            return_value=(mock_device, -60),  # Returns tuple (device, rssi)
        ),
        patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test TL100"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "validate"


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery triggers config flow."""
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

    service_info = BluetoothServiceInfoBleak(
        name="TL100",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
        device=BLEDevice("AA:BB:CC:DD:EE:FF", "TL100"),
        advertisement=AdvertisementData(
            local_name="TL100",
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            rssi=-60,
            tx_power=None,
            platform_data=(),
        ),
        time=0,
        connectable=True,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


async def test_connection_test_failure(hass: HomeAssistant) -> None:
    """Test connection test failure."""
    with (
        patch(
            "custom_components.beurer_daylight_lamps.config_flow.discover",
            return_value=[],
        ),
        patch(
            "custom_components.beurer_daylight_lamps.config_flow.get_device",
            return_value=(None, None),  # Device not found
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "validate"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_abort_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if device already configured."""
    # First, add a config entry
    entry = MagicMock()
    entry.unique_id = "aa:bb:cc:dd:ee:ff"
    hass.config_entries._entries = {"test": entry}

    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"
    mock_device.name = "TL100"

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.discover",
        return_value=[mock_device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Select the device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def test_is_valid_mac() -> None:
    """Test MAC address validation."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()

    # Valid formats
    assert flow._is_valid_mac("AA:BB:CC:DD:EE:FF") is True
    assert flow._is_valid_mac("AA-BB-CC-DD-EE-FF") is True
    assert flow._is_valid_mac("AABBCCDDEEFF") is True
    assert flow._is_valid_mac("aabbccddeeff") is True

    # Invalid formats
    assert flow._is_valid_mac("invalid") is False
    assert flow._is_valid_mac("AA:BB:CC:DD:EE") is False
    assert flow._is_valid_mac("AA:BB:CC:DD:EE:FF:GG") is False
    assert flow._is_valid_mac("GGHHIIJJKKLL") is False
    assert flow._is_valid_mac("") is False
