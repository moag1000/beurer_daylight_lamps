"""Test Beurer Daylight Lamps repairs module."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.repairs import (
    DeviceNotFoundRepairFlow,
    InitializationFailedRepairFlow,
    async_create_fix_flow,
)


class TestDeviceNotFoundRepairFlow:
    """Tests for DeviceNotFoundRepairFlow class."""

    @pytest.fixture
    def repair_flow(self) -> DeviceNotFoundRepairFlow:
        """Create a repair flow instance."""
        return DeviceNotFoundRepairFlow(
            issue_id="device_not_found_test_entry",
            data={"name": "Test Lamp", "mac": "AA:BB:CC:DD:EE:FF"},
        )

    @pytest.mark.asyncio
    async def test_init_extracts_entry_id(
        self, hass: HomeAssistant, repair_flow: DeviceNotFoundRepairFlow
    ) -> None:
        """Test that init step extracts entry ID from issue ID."""
        repair_flow.hass = hass

        result = await repair_flow.async_step_init()

        assert repair_flow._entry_id == "test_entry"

    @pytest.mark.asyncio
    async def test_confirm_shows_form(
        self, hass: HomeAssistant, repair_flow: DeviceNotFoundRepairFlow
    ) -> None:
        """Test that confirm step shows form initially."""
        repair_flow.hass = hass

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test Lamp"}

        with patch.object(
            hass.config_entries, "async_get_entry", return_value=mock_entry
        ):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_aborts_if_entry_not_found(
        self, hass: HomeAssistant, repair_flow: DeviceNotFoundRepairFlow
    ) -> None:
        """Test that confirm aborts if config entry not found."""
        repair_flow.hass = hass

        with patch.object(hass.config_entries, "async_get_entry", return_value=None):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm(user_input={})

        assert result["type"] == "abort"
        assert result["reason"] == "entry_not_found"

    @pytest.mark.asyncio
    async def test_confirm_success_when_device_found(
        self, hass: HomeAssistant, repair_flow: DeviceNotFoundRepairFlow
    ) -> None:
        """Test that confirm succeeds when device is found."""
        repair_flow.hass = hass

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test Lamp"}

        # Create mock BLE device
        mock_ble_device = MagicMock()
        mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

        with (
            patch.object(
                hass.config_entries, "async_get_entry", return_value=mock_entry
            ),
            patch.object(
                hass.config_entries, "async_reload", new_callable=AsyncMock
            ) as mock_reload,
            patch(
                "custom_components.beurer_daylight_lamps.repairs.bluetooth.async_ble_device_from_address",
                return_value=mock_ble_device,
            ),
            patch(
                "custom_components.beurer_daylight_lamps.repairs.ir.async_delete_issue"
            ) as mock_delete_issue,
        ):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm(user_input={})

        assert result["type"] == "create_entry"
        mock_delete_issue.assert_called_once()
        mock_reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_shows_error_when_device_not_found(
        self, hass: HomeAssistant, repair_flow: DeviceNotFoundRepairFlow
    ) -> None:
        """Test that confirm shows error when device still not found."""
        repair_flow.hass = hass

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.data = {CONF_MAC: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Test Lamp"}

        with (
            patch.object(
                hass.config_entries, "async_get_entry", return_value=mock_entry
            ),
            patch(
                "custom_components.beurer_daylight_lamps.repairs.bluetooth.async_ble_device_from_address",
                return_value=None,
            ),
        ):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm(user_input={})

        assert result["type"] == "form"
        assert result["errors"] == {"base": "still_not_found"}


class TestInitializationFailedRepairFlow:
    """Tests for InitializationFailedRepairFlow class."""

    @pytest.fixture
    def repair_flow(self) -> InitializationFailedRepairFlow:
        """Create a repair flow instance."""
        return InitializationFailedRepairFlow(
            issue_id="initialization_failed_test_entry",
            data={
                "name": "Test Lamp",
                "mac": "AA:BB:CC:DD:EE:FF",
                "error": "Connection timeout",
            },
        )

    @pytest.mark.asyncio
    async def test_init_extracts_entry_id(
        self, hass: HomeAssistant, repair_flow: InitializationFailedRepairFlow
    ) -> None:
        """Test that init step extracts entry ID from issue ID."""
        repair_flow.hass = hass

        result = await repair_flow.async_step_init()

        assert repair_flow._entry_id == "test_entry"

    @pytest.mark.asyncio
    async def test_confirm_shows_form(
        self, hass: HomeAssistant, repair_flow: InitializationFailedRepairFlow
    ) -> None:
        """Test that confirm step shows form initially."""
        repair_flow.hass = hass

        repair_flow._entry_id = "test_entry"
        result = await repair_flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_aborts_if_entry_not_found(
        self, hass: HomeAssistant, repair_flow: InitializationFailedRepairFlow
    ) -> None:
        """Test that confirm aborts if config entry not found."""
        repair_flow.hass = hass

        with patch.object(hass.config_entries, "async_get_entry", return_value=None):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm(user_input={})

        assert result["type"] == "abort"
        assert result["reason"] == "entry_not_found"

    @pytest.mark.asyncio
    async def test_confirm_success_on_reload(
        self, hass: HomeAssistant, repair_flow: InitializationFailedRepairFlow
    ) -> None:
        """Test that confirm succeeds when reload succeeds."""
        repair_flow.hass = hass

        # Create mock config entry
        mock_entry = MagicMock()

        with (
            patch.object(
                hass.config_entries, "async_get_entry", return_value=mock_entry
            ),
            patch.object(
                hass.config_entries, "async_reload", new_callable=AsyncMock
            ) as mock_reload,
            patch(
                "custom_components.beurer_daylight_lamps.repairs.ir.async_delete_issue"
            ) as mock_delete_issue,
        ):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm(user_input={})

        assert result["type"] == "create_entry"
        mock_delete_issue.assert_called_once()
        mock_reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_shows_error_on_reload_failure(
        self, hass: HomeAssistant, repair_flow: InitializationFailedRepairFlow
    ) -> None:
        """Test that confirm shows error when reload fails."""
        repair_flow.hass = hass

        # Create mock config entry
        mock_entry = MagicMock()

        with (
            patch.object(
                hass.config_entries, "async_get_entry", return_value=mock_entry
            ),
            patch.object(
                hass.config_entries,
                "async_reload",
                new_callable=AsyncMock,
                side_effect=Exception("Reload failed"),
            ),
            patch(
                "custom_components.beurer_daylight_lamps.repairs.ir.async_delete_issue"
            ),
        ):
            repair_flow._entry_id = "test_entry"
            result = await repair_flow.async_step_confirm(user_input={})

        assert result["type"] == "form"
        assert result["errors"] == {"base": "reload_failed"}


class TestAsyncCreateFixFlow:
    """Tests for async_create_fix_flow function."""

    @pytest.mark.asyncio
    async def test_creates_device_not_found_flow(
        self, hass: HomeAssistant
    ) -> None:
        """Test creating device not found repair flow."""
        flow = await async_create_fix_flow(
            hass,
            "device_not_found_test_entry",
            {"name": "Test Lamp"},
        )

        assert isinstance(flow, DeviceNotFoundRepairFlow)

    @pytest.mark.asyncio
    async def test_creates_initialization_failed_flow(
        self, hass: HomeAssistant
    ) -> None:
        """Test creating initialization failed repair flow."""
        flow = await async_create_fix_flow(
            hass,
            "initialization_failed_test_entry",
            {"name": "Test Lamp", "error": "Connection failed"},
        )

        assert isinstance(flow, InitializationFailedRepairFlow)

    @pytest.mark.asyncio
    async def test_raises_for_unknown_issue(self, hass: HomeAssistant) -> None:
        """Test that unknown issue type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown issue type"):
            await async_create_fix_flow(
                hass,
                "unknown_issue_test_entry",
                {},
            )
