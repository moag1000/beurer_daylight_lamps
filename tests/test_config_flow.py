"""Test the Beurer Daylight Lamps config flow."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak import BleakError

from homeassistant import config_entries
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.beurer_daylight_lamps.const import DOMAIN


# =============================================================================
# MAC Validation Tests (No HA dependencies - Pure Unit Tests)
# =============================================================================


def test_is_valid_mac_colon_format() -> None:
    """Test MAC validation with colon separators."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("AA:BB:CC:DD:EE:FF") is True
    assert flow._is_valid_mac("aa:bb:cc:dd:ee:ff") is True
    assert flow._is_valid_mac("11:22:33:44:55:66") is True


def test_is_valid_mac_dash_format() -> None:
    """Test MAC validation with dash separators."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("AA-BB-CC-DD-EE-FF") is True
    assert flow._is_valid_mac("aa-bb-cc-dd-ee-ff") is True


def test_is_valid_mac_no_separator() -> None:
    """Test MAC validation without separators."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("AABBCCDDEEFF") is True
    assert flow._is_valid_mac("aabbccddeeff") is True


def test_is_valid_mac_invalid_short() -> None:
    """Test MAC validation rejects short addresses."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("AA:BB:CC:DD:EE") is False
    assert flow._is_valid_mac("AABBCC") is False


def test_is_valid_mac_invalid_long() -> None:
    """Test MAC validation rejects long addresses."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("AA:BB:CC:DD:EE:FF:GG") is False
    assert flow._is_valid_mac("AABBCCDDEEFF00") is False


def test_is_valid_mac_invalid_chars() -> None:
    """Test MAC validation rejects invalid characters."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("GGHHIIJJKKLL") is False
    assert flow._is_valid_mac("XX:YY:ZZ:11:22:33") is False


def test_is_valid_mac_empty() -> None:
    """Test MAC validation rejects empty strings."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("") is False


def test_is_valid_mac_random_text() -> None:
    """Test MAC validation rejects random text."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("invalid") is False
    assert flow._is_valid_mac("not a mac address") is False


def test_is_valid_mac_mixed_case() -> None:
    """Test MAC validation with mixed case."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._is_valid_mac("Aa:Bb:Cc:Dd:Ee:Ff") is True
    assert flow._is_valid_mac("aAbBcCdDeEfF") is True


# =============================================================================
# Config Flow Initialization Tests (No HA dependencies)
# =============================================================================


def test_config_flow_init() -> None:
    """Test config flow initialization."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow._mac is None
    assert flow._name is None
    assert flow._instance is None
    assert flow._discovery_info is None
    assert flow._ble_device is None
    assert flow._rssi is None
    assert flow._reauth_entry is None
    assert flow._reconfigure_entry is None
    assert flow._discovered_devices == {}


def test_config_flow_version() -> None:
    """Test config flow version is set correctly."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    assert flow.VERSION == 1


def test_config_flow_domain() -> None:
    """Test config flow domain is set correctly."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    # Check DOMAIN constant
    assert DOMAIN == "beurer_daylight_lamps"


# =============================================================================
# _test_connection Method Tests (Direct method testing with mocks)
# =============================================================================


@pytest.mark.asyncio
async def test_connection_with_cached_device(hass: HomeAssistant) -> None:
    """Test connection test uses cached BLE device."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"

    mock_instance = MagicMock()
    mock_instance.is_on = False
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is True
    mock_instance.update.assert_called_once()
    mock_instance.turn_on.assert_called_once()
    mock_instance.turn_off.assert_called_once()
    mock_instance.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_connection_without_cached_device_not_found(hass: HomeAssistant) -> None:
    """Test connection fails when device not found."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = None

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result = await flow._test_connection()

    assert result is False


@pytest.mark.asyncio
async def test_connection_bleak_error(hass: HomeAssistant) -> None:
    """Test connection handles BleakError."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.update = AsyncMock(side_effect=BleakError("Connection failed"))
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is False
    mock_instance.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_connection_timeout_error(hass: HomeAssistant) -> None:
    """Test connection handles TimeoutError."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.update = AsyncMock(side_effect=TimeoutError("Timed out"))
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is False


@pytest.mark.asyncio
async def test_connection_asyncio_timeout(hass: HomeAssistant) -> None:
    """Test connection handles asyncio.TimeoutError."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.update = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is False


@pytest.mark.asyncio
async def test_connection_os_error(hass: HomeAssistant) -> None:
    """Test connection handles OSError."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.update = AsyncMock(side_effect=OSError("Bluetooth unavailable"))
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is False


@pytest.mark.asyncio
async def test_connection_value_error(hass: HomeAssistant) -> None:
    """Test connection handles ValueError."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.update = AsyncMock(side_effect=ValueError("Invalid device"))
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is False


@pytest.mark.asyncio
async def test_connection_toggles_off_lamp(hass: HomeAssistant) -> None:
    """Test connection toggles lamp that is currently off."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.is_on = False  # Lamp is OFF
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is True
    # When lamp is off: turn on first, then off
    mock_instance.turn_on.assert_called_once()
    mock_instance.turn_off.assert_called_once()


@pytest.mark.asyncio
async def test_connection_toggles_on_lamp(hass: HomeAssistant) -> None:
    """Test connection toggles lamp that is already on."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.is_on = True  # Lamp is ON
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is True
    # When lamp is on: turn off first, then on
    mock_instance.turn_off.assert_called_once()
    mock_instance.turn_on.assert_called_once()


@pytest.mark.asyncio
async def test_connection_disconnect_error_ignored(hass: HomeAssistant) -> None:
    """Test disconnect errors are handled gracefully."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.is_on = False
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock(side_effect=BleakError("Disconnect failed"))

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        # Should succeed even if disconnect fails
        result = await flow._test_connection()

    assert result is True


@pytest.mark.asyncio
async def test_connection_with_non_connectable_device(hass: HomeAssistant) -> None:
    """Test connection with non-connectable device found."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_device.address = "AA:BB:CC:DD:EE:FF"

    mock_instance = MagicMock()
    mock_instance.is_on = False
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = None  # No cached device

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_ble_device_from_address",
        side_effect=[None, mock_device],  # First call returns None, second returns device
    ), patch(
        "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_last_service_info",
        return_value=None,
    ), patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        result = await flow._test_connection()

    assert result is True


@pytest.mark.asyncio
async def test_connection_cleans_up_instance(hass: HomeAssistant) -> None:
    """Test connection cleans up instance after test."""
    from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

    mock_device = MagicMock()
    mock_instance = MagicMock()
    mock_instance.is_on = False
    mock_instance.update = AsyncMock()
    mock_instance.turn_on = AsyncMock()
    mock_instance.turn_off = AsyncMock()
    mock_instance.disconnect = AsyncMock()

    flow = BeurerConfigFlow()
    flow.hass = hass
    flow._mac = "AA:BB:CC:DD:EE:FF"
    flow._ble_device = mock_device
    flow._rssi = -60

    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
        return_value=mock_instance,
    ):
        await flow._test_connection()

    # Instance should be cleaned up after test
    assert flow._instance is None


# =============================================================================
# Integration Tests (Require HA Bluetooth - skip in CI)
# These tests use the full HA config_entries.flow infrastructure
# =============================================================================


@pytest.mark.skip(reason="Requires bluetooth dependency - usb setup fails in CI")
async def test_user_step_no_devices_goes_to_manual(hass: HomeAssistant) -> None:
    """Test user step redirects to manual when no devices found."""
    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.skip(reason="Requires bluetooth dependency - usb setup fails in CI")
async def test_manual_step_invalid_mac(hass: HomeAssistant) -> None:
    """Test manual step with invalid MAC address."""
    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "invalid", CONF_NAME: "Test Lamp"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {CONF_MAC: "invalid_mac"}


@pytest.mark.skip(reason="Requires bluetooth dependency - usb setup fails in CI")
async def test_bluetooth_discovery_step(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery triggers config flow."""
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

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


@pytest.mark.skip(reason="Requires bluetooth dependency - usb setup fails in CI")
async def test_validate_step_connection_success_creates_entry(
    hass: HomeAssistant,
) -> None:
    """Test successful validation creates config entry."""
    with patch(
        "custom_components.beurer_daylight_lamps.config_flow.BeurerConfigFlow._test_connection",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "custom_components.beurer_daylight_lamps.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test TL100"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"flicker": True},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test TL100"


# =============================================================================
# Additional Config Flow Tests (Direct method testing)
# =============================================================================


class TestAsyncStepBluetooth:
    """Tests for async_step_bluetooth."""

    @pytest.mark.asyncio
    async def test_bluetooth_discovery_sets_device_info(self, hass: HomeAssistant) -> None:
        """Test bluetooth discovery extracts device info correctly."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"

        mock_discovery = MagicMock()
        mock_discovery.name = "TL100"
        mock_discovery.address = "AA:BB:CC:DD:EE:FF"
        mock_discovery.rssi = -65
        mock_discovery.device = mock_device

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow.context = {}

        with patch.object(flow, "async_set_unique_id", new_callable=AsyncMock), \
             patch.object(flow, "_abort_if_unique_id_configured"), \
             patch.object(flow, "async_step_bluetooth_confirm", new_callable=AsyncMock, return_value={}):
            await flow.async_step_bluetooth(mock_discovery)

        assert flow._mac == "AA:BB:CC:DD:EE:FF"
        assert flow._name == "TL100"
        assert flow._ble_device == mock_device
        assert flow._rssi == -65

    @pytest.mark.asyncio
    async def test_bluetooth_discovery_fallback_name(self, hass: HomeAssistant) -> None:
        """Test bluetooth discovery uses fallback name when device name is None."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_discovery = MagicMock()
        mock_discovery.name = None
        mock_discovery.address = "AA:BB:CC:DD:EE:FF"
        mock_discovery.rssi = -70
        mock_discovery.device = MagicMock()

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow.context = {}

        with patch.object(flow, "async_set_unique_id", new_callable=AsyncMock), \
             patch.object(flow, "_abort_if_unique_id_configured"), \
             patch.object(flow, "async_step_bluetooth_confirm", new_callable=AsyncMock, return_value={}):
            await flow.async_step_bluetooth(mock_discovery)

        # Should use fallback name with last 8 chars of address
        assert flow._name == "Beurer DD:EE:FF"


class TestAsyncStepBluetoothConfirm:
    """Tests for async_step_bluetooth_confirm."""

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_no_input_shows_form(self, hass: HomeAssistant) -> None:
        """Test bluetooth confirm shows form when no input."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._name = "Test Lamp"

        result = await flow.async_step_bluetooth_confirm(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "bluetooth_confirm"

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_with_custom_name(self, hass: HomeAssistant) -> None:
        """Test bluetooth confirm uses custom name from user input."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._name = "TL100"

        with patch.object(flow, "async_step_validate", new_callable=AsyncMock, return_value={"type": "form"}):
            await flow.async_step_bluetooth_confirm(user_input={CONF_NAME: "My Custom Lamp"})

        assert flow._name == "My Custom Lamp"

    @pytest.mark.asyncio
    async def test_bluetooth_confirm_keeps_default_name(self, hass: HomeAssistant) -> None:
        """Test bluetooth confirm keeps default name when no custom name provided."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._name = "TL100"

        with patch.object(flow, "async_step_validate", new_callable=AsyncMock, return_value={"type": "form"}):
            await flow.async_step_bluetooth_confirm(user_input={CONF_NAME: ""})

        # Name should remain as original
        assert flow._name == "TL100"


class TestAsyncStepManual:
    """Tests for async_step_manual."""

    @pytest.mark.asyncio
    async def test_manual_no_input_shows_form(self, hass: HomeAssistant) -> None:
        """Test manual step shows form when no input."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass

        result = await flow.async_step_manual(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "manual"

    @pytest.mark.asyncio
    async def test_manual_invalid_mac_shows_error(self, hass: HomeAssistant) -> None:
        """Test manual step shows error for invalid MAC."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass

        result = await flow.async_step_manual(
            user_input={CONF_MAC: "invalid-mac", CONF_NAME: "Test Lamp"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "manual"
        assert result["errors"][CONF_MAC] == "invalid_mac"

    @pytest.mark.asyncio
    async def test_manual_valid_mac_proceeds(self, hass: HomeAssistant) -> None:
        """Test manual step proceeds with valid MAC."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass

        with patch.object(flow, "async_set_unique_id", new_callable=AsyncMock), \
             patch.object(flow, "_abort_if_unique_id_configured"), \
             patch.object(flow, "async_step_validate", new_callable=AsyncMock, return_value={"type": "form"}):
            await flow.async_step_manual(
                user_input={CONF_MAC: "aa:bb:cc:dd:ee:ff", CONF_NAME: "Test Lamp"}
            )

        # MAC should be normalized to uppercase
        assert flow._mac == "AA:BB:CC:DD:EE:FF"
        assert flow._name == "Test Lamp"

    @pytest.mark.asyncio
    async def test_manual_mac_normalized(self, hass: HomeAssistant) -> None:
        """Test manual step normalizes MAC address."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass

        with patch.object(flow, "async_set_unique_id", new_callable=AsyncMock), \
             patch.object(flow, "_abort_if_unique_id_configured"), \
             patch.object(flow, "async_step_validate", new_callable=AsyncMock, return_value={}):
            await flow.async_step_manual(
                user_input={CONF_MAC: "  aa-bb-cc-dd-ee-ff  ", CONF_NAME: "Test"}
            )

        assert flow._mac == "AA-BB-CC-DD-EE-FF"


class TestAsyncStepValidate:
    """Tests for async_step_validate."""

    @pytest.mark.asyncio
    async def test_validate_connection_failure_shows_retry(self, hass: HomeAssistant) -> None:
        """Test validate shows retry form on connection failure."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"

        with patch.object(flow, "_test_connection", new_callable=AsyncMock, return_value=False):
            result = await flow.async_step_validate(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "validate"
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_validate_connection_success_shows_flicker(self, hass: HomeAssistant) -> None:
        """Test validate shows flicker confirmation on success."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"

        with patch.object(flow, "_test_connection", new_callable=AsyncMock, return_value=True):
            result = await flow.async_step_validate(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "validate"
        # Should ask about flicker (success), not retry (failure)
        assert "flicker" in str(result.get("data_schema", ""))

    @pytest.mark.asyncio
    async def test_validate_flicker_confirmed_creates_entry(self, hass: HomeAssistant) -> None:
        """Test validate creates entry when flicker is confirmed."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._name = "My Lamp"
        flow._reconfigure_entry = None

        result = await flow.async_step_validate(user_input={"flicker": True})

        assert result["type"] == "create_entry"
        assert result["title"] == "My Lamp"
        assert result["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_validate_flicker_confirmed_default_name(self, hass: HomeAssistant) -> None:
        """Test validate uses default name when none provided."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._name = None  # No name provided
        flow._reconfigure_entry = None

        result = await flow.async_step_validate(user_input={"flicker": True})

        assert result["type"] == "create_entry"
        assert result["title"] == "Beurer Lamp"

    @pytest.mark.asyncio
    async def test_validate_retry_false_aborts(self, hass: HomeAssistant) -> None:
        """Test validate aborts when user chooses not to retry."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass

        result = await flow.async_step_validate(user_input={"retry": False})

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_validate_reconfigure_updates_entry(self, hass: HomeAssistant) -> None:
        """Test validate updates entry during reconfigure."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._name = "Updated Lamp"
        flow._reconfigure_entry = mock_entry

        with patch.object(
            hass.config_entries, "async_update_entry"
        ) as mock_update, patch.object(
            hass.config_entries, "async_reload", new_callable=AsyncMock
        ):
            result = await flow.async_step_validate(user_input={"flicker": True})

        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"
        mock_update.assert_called_once()


class TestAsyncStepUser:
    """Tests for async_step_user."""

    @pytest.mark.asyncio
    async def test_user_step_manual_mac_redirects(self, hass: HomeAssistant) -> None:
        """Test user step redirects to manual when MANUAL_MAC selected."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow, MANUAL_MAC

        flow = BeurerConfigFlow()
        flow.hass = hass

        with patch.object(flow, "async_step_manual", new_callable=AsyncMock, return_value={"type": "form"}):
            result = await flow.async_step_user(
                user_input={CONF_MAC: MANUAL_MAC, CONF_NAME: "Test"}
            )

        # Should redirect to manual step
        assert result == {"type": "form"}

    @pytest.mark.asyncio
    async def test_user_step_uses_cached_device(self, hass: HomeAssistant) -> None:
        """Test user step uses cached device info when available."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_info = MagicMock()
        mock_info.device = mock_device
        mock_info.rssi = -55

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._discovered_devices = {"AA:BB:CC:DD:EE:FF": mock_info}

        with patch.object(flow, "async_set_unique_id", new_callable=AsyncMock), \
             patch.object(flow, "_abort_if_unique_id_configured"), \
             patch.object(flow, "async_step_validate", new_callable=AsyncMock, return_value={}):
            await flow.async_step_user(
                user_input={CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test"}
            )

        assert flow._ble_device == mock_device
        assert flow._rssi == -55


class TestAsyncStepReauth:
    """Tests for reauth flow."""

    @pytest.mark.asyncio
    async def test_reauth_step_extracts_entry_data(self, hass: HomeAssistant) -> None:
        """Test reauth step extracts entry data."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_entry = MagicMock()
        mock_entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Old Lamp"}

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "test_id"}

        with patch.object(
            hass.config_entries, "async_get_entry", return_value=mock_entry
        ), patch.object(
            flow, "async_step_reauth_confirm", new_callable=AsyncMock, return_value={}
        ):
            await flow.async_step_reauth(
                entry_data={CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Old Lamp"}
            )

        assert flow._mac == "AA:BB:CC:DD:EE:FF"
        assert flow._name == "Old Lamp"
        assert flow._reauth_entry == mock_entry

    @pytest.mark.asyncio
    async def test_reauth_confirm_no_input_shows_form(self, hass: HomeAssistant) -> None:
        """Test reauth confirm shows form when no input."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._name = "Test Lamp"

        result = await flow.async_step_reauth_confirm(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

    @pytest.mark.asyncio
    async def test_reauth_confirm_success_updates_entry(self, hass: HomeAssistant) -> None:
        """Test reauth confirm updates entry on success."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._name = "Test Lamp"
        flow._reauth_entry = mock_entry

        with patch.object(flow, "_test_connection", new_callable=AsyncMock, return_value=True), \
             patch.object(hass.config_entries, "async_update_entry") as mock_update, \
             patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
            result = await flow.async_step_reauth_confirm(user_input={})

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_reauth_confirm_failure_shows_error(self, hass: HomeAssistant) -> None:
        """Test reauth confirm shows error on failure."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._name = "Test Lamp"

        with patch.object(flow, "_test_connection", new_callable=AsyncMock, return_value=False):
            result = await flow.async_step_reauth_confirm(user_input={})

        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"


class TestAsyncStepReconfigure:
    """Tests for reconfigure flow."""

    @pytest.mark.asyncio
    async def test_reconfigure_no_input_shows_form(self, hass: HomeAssistant) -> None:
        """Test reconfigure shows form when no input."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_entry = MagicMock()
        mock_entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Old Name"}

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "test_id"}

        with patch.object(hass.config_entries, "async_get_entry", return_value=mock_entry):
            result = await flow.async_step_reconfigure(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"
        assert flow._mac == "AA:BB:CC:DD:EE:FF"
        assert flow._name == "Old Name"

    @pytest.mark.asyncio
    async def test_reconfigure_with_input_updates_name(self, hass: HomeAssistant) -> None:
        """Test reconfigure updates name from input."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_entry = MagicMock()
        mock_entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Old Name"}

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "test_id"}
        flow._reconfigure_entry = mock_entry

        with patch.object(hass.config_entries, "async_get_entry", return_value=mock_entry), \
             patch.object(flow, "async_step_validate", new_callable=AsyncMock, return_value={}):
            await flow.async_step_reconfigure(user_input={CONF_NAME: "New Name"})

        assert flow._name == "New Name"


class TestTestConnectionWithServiceInfo:
    """Tests for _test_connection with service info retrieval."""

    @pytest.mark.asyncio
    async def test_connection_gets_rssi_from_service_info(self, hass: HomeAssistant) -> None:
        """Test connection retrieves RSSI from service info."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"

        mock_service_info = MagicMock()
        mock_service_info.rssi = -72

        mock_instance = MagicMock()
        mock_instance.is_on = False
        mock_instance.update = AsyncMock()
        mock_instance.turn_on = AsyncMock()
        mock_instance.turn_off = AsyncMock()
        mock_instance.disconnect = AsyncMock()

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._ble_device = None  # No cached device

        with patch(
            "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_ble_device_from_address",
            return_value=mock_device,
        ), patch(
            "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_last_service_info",
            return_value=mock_service_info,
        ), patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ):
            result = await flow._test_connection()

        assert result is True
        assert flow._rssi == -72

    @pytest.mark.asyncio
    async def test_connection_handles_no_service_info(self, hass: HomeAssistant) -> None:
        """Test connection handles missing service info."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"

        mock_instance = MagicMock()
        mock_instance.is_on = False
        mock_instance.update = AsyncMock()
        mock_instance.turn_on = AsyncMock()
        mock_instance.turn_off = AsyncMock()
        mock_instance.disconnect = AsyncMock()

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._ble_device = None

        with patch(
            "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_ble_device_from_address",
            return_value=mock_device,
        ), patch(
            "custom_components.beurer_daylight_lamps.config_flow.bluetooth.async_last_service_info",
            return_value=None,
        ), patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ):
            result = await flow._test_connection()

        assert result is True
        assert flow._rssi is None

    @pytest.mark.asyncio
    async def test_connection_timeout_in_asyncio_timeout(self, hass: HomeAssistant) -> None:
        """Test connection handles asyncio.timeout expiration."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()

        mock_instance = MagicMock()
        # Simulate timeout during update()
        async def slow_update():
            await asyncio.sleep(100)  # Very slow

        mock_instance.update = slow_update
        mock_instance.disconnect = AsyncMock()

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._ble_device = mock_device
        flow._rssi = -60

        with patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ), patch("asyncio.timeout", side_effect=asyncio.TimeoutError()):
            result = await flow._test_connection()

        assert result is False


class TestConnectionDisconnectErrors:
    """Tests for disconnect error handling in _test_connection."""

    @pytest.mark.asyncio
    async def test_disconnect_timeout_error_ignored(self, hass: HomeAssistant) -> None:
        """Test disconnect TimeoutError is handled gracefully."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_instance = MagicMock()
        mock_instance.is_on = False
        mock_instance.update = AsyncMock()
        mock_instance.turn_on = AsyncMock()
        mock_instance.turn_off = AsyncMock()
        mock_instance.disconnect = AsyncMock(side_effect=TimeoutError("Disconnect timeout"))

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._ble_device = mock_device
        flow._rssi = -60

        with patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ):
            result = await flow._test_connection()

        assert result is True  # Should succeed despite disconnect error

    @pytest.mark.asyncio
    async def test_disconnect_os_error_ignored(self, hass: HomeAssistant) -> None:
        """Test disconnect OSError is handled gracefully."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_instance = MagicMock()
        mock_instance.is_on = True  # Test with lamp ON this time
        mock_instance.update = AsyncMock()
        mock_instance.turn_on = AsyncMock()
        mock_instance.turn_off = AsyncMock()
        mock_instance.disconnect = AsyncMock(side_effect=OSError("Adapter unavailable"))

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._ble_device = mock_device
        flow._rssi = -60

        with patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ):
            result = await flow._test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_asyncio_timeout_error_ignored(self, hass: HomeAssistant) -> None:
        """Test disconnect asyncio.TimeoutError is handled gracefully."""
        from custom_components.beurer_daylight_lamps.config_flow import BeurerConfigFlow

        mock_device = MagicMock()
        mock_instance = MagicMock()
        mock_instance.is_on = False
        mock_instance.update = AsyncMock()
        mock_instance.turn_on = AsyncMock()
        mock_instance.turn_off = AsyncMock()
        mock_instance.disconnect = AsyncMock(side_effect=asyncio.TimeoutError())

        flow = BeurerConfigFlow()
        flow.hass = hass
        flow._mac = "AA:BB:CC:DD:EE:FF"
        flow._ble_device = mock_device
        flow._rssi = -60

        with patch(
            "custom_components.beurer_daylight_lamps.config_flow.BeurerInstance",
            return_value=mock_instance,
        ):
            result = await flow._test_connection()

        assert result is True
