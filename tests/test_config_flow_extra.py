"""Extra coverage for the config flow (device picker, GATT checks, options)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beurer_daylight_lamps.config_flow import (
    MANUAL_MAC,
    BeurerConfigFlow,
)
from custom_components.beurer_daylight_lamps.const import DOMAIN

CF = "custom_components.beurer_daylight_lamps.config_flow"


def _info(address: str, name: str | None, rssi: int | None = -60) -> MagicMock:
    info = MagicMock()
    info.address = address
    info.name = name
    info.rssi = rssi
    info.device = MagicMock(name=f"dev-{address}")
    return info


def _flow(hass: HomeAssistant, source: str = "user") -> BeurerConfigFlow:
    flow = BeurerConfigFlow()
    flow.hass = hass
    flow.context = {"source": source}
    return flow


class TestUserStep:
    """Device picker built from HA's Bluetooth cache."""

    async def test_lists_beurer_devices(self, hass: HomeAssistant) -> None:
        MockConfigEntry(domain=DOMAIN, unique_id="11:11:11:11:11:11").add_to_hass(hass)
        connectable = [
            _info("AA:AA:AA:AA:AA:AA", "TL100_1"),
            _info("11:11:11:11:11:11", "TL100_configured"),
            _info("CC:CC:CC:CC:CC:CC", "Other device"),
            _info("DD:DD:DD:DD:DD:DD", None),
        ]
        passive = [
            _info("AA:AA:AA:AA:AA:AA", "TL100_1"),
            _info("BB:BB:BB:BB:BB:BB", "WL90_2", rssi=None),
        ]
        flow = _flow(hass)
        with patch(
            f"{CF}.async_discovered_service_info",
            side_effect=lambda _h, connectable: (
                connectable_list if connectable else passive
            ),
        ):
            connectable_list = connectable
            result = await flow.async_step_user()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        options = result["data_schema"].schema[CONF_MAC].container
        assert options == {
            "AA:AA:AA:AA:AA:AA": "TL100_1 (-60 dBm)",
            "BB:BB:BB:BB:BB:BB": "WL90_2 (via Proxy)",
            MANUAL_MAC: "Enter MAC manually",
        }

    async def test_pick_manual(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        result = await flow.async_step_user({CONF_MAC: MANUAL_MAC, CONF_NAME: ""})
        assert result["step_id"] == "manual"

    async def test_pick_cached_device(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        info = _info("AA:AA:AA:AA:AA:AA", "TL100_1", rssi=-50)
        flow._discovered_devices = {info.address: info}
        with patch.object(
            flow, "async_step_validate", new=AsyncMock(return_value={"ok": 1})
        ):
            assert await flow.async_step_user(
                {CONF_MAC: info.address, CONF_NAME: "Bedroom"}
            ) == {"ok": 1}
        assert flow._ble_device is info.device
        assert flow._rssi == -50
        assert flow._name == "Bedroom"
        assert flow.unique_id == "aa:aa:aa:aa:aa:aa"


class TestValidateStep:
    """Validate step branches."""

    async def test_no_gatt_adapter(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        flow._mac = "AA:AA:AA:AA:AA:AA"
        with patch(
            f"{CF}.bluetooth.async_ble_device_from_address",
            side_effect=lambda _h, _m, connectable: None if connectable else object(),
        ):
            result = await flow.async_step_validate()
        assert result["errors"] == {"base": "no_gatt_adapter"}

    async def test_retry_false_aborts(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        result = await flow.async_step_validate({"retry": False})
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"

    async def test_connection_failed_shows_retry(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        flow._mac = "AA:AA:AA:AA:AA:AA"
        with (
            patch(
                f"{CF}.bluetooth.async_ble_device_from_address",
                return_value=object(),
            ),
            patch.object(flow, "_test_connection", new=AsyncMock(return_value=False)),
        ):
            result = await flow.async_step_validate()
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_flicker_creates_entry(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        flow._mac = "AA:AA:AA:AA:AA:AA"
        flow._name = None
        result = await flow.async_step_validate({"flicker": True})
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Beurer Lamp"


class TestEnsureInstance:
    """Finding the BLE device through HA's Bluetooth stack."""

    def test_existing_instance(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        flow._instance = MagicMock()
        assert flow._ensure_instance_from_bluetooth()

    def test_no_mac(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        assert not flow._ensure_instance_from_bluetooth()

    def test_non_connectable_fallback(self, hass: HomeAssistant) -> None:
        flow = _flow(hass)
        flow._mac = "AA:AA:AA:AA:AA:AA"
        device = object()
        last = MagicMock(rssi=-71)
        with (
            patch(
                f"{CF}.bluetooth.async_ble_device_from_address",
                side_effect=lambda _h, _m, connectable: None if connectable else device,
            ),
            patch(
                f"{CF}.bluetooth.async_last_service_info",
                side_effect=lambda _h, _m, connectable=True: (
                    None if connectable else last
                ),
            ),
            patch(f"{CF}.BeurerInstance") as inst_cls,
        ):
            assert flow._ensure_instance_from_bluetooth()
        inst_cls.assert_called_once_with(device, -71, hass)
        assert flow._rssi == -71


class TestTimeoutLogging:
    """Timeout reasons."""

    @pytest.mark.parametrize(
        ("conn", "passive", "text"),
        [
            (False, True, "no GATT-capable adapter"),
            (False, False, "not visible"),
            (True, True, "slots may be full"),
        ],
    )
    def test_reasons(
        self,
        hass: HomeAssistant,
        caplog: pytest.LogCaptureFixture,
        conn: bool,
        passive: bool,
        text: str,
    ) -> None:
        flow = _flow(hass)
        flow._mac = "AA:AA:AA:AA:AA:AA"
        flow._ble_device = MagicMock()
        flow._ble_device.name = "hci0"
        with patch(
            f"{CF}.bluetooth.async_ble_device_from_address",
            side_effect=lambda _h, _m, connectable: (
                object() if (conn if connectable else passive) else None
            ),
        ):
            flow._handle_connection_timeout()
        assert text in caplog.text
        assert "hci0" in caplog.text

    def test_no_mac(self, hass: HomeAssistant, caplog) -> None:
        _flow(hass)._handle_connection_timeout()
        assert "timed out" not in caplog.text


async def test_connection_without_mac(hass: HomeAssistant) -> None:
    assert not await _flow(hass)._test_connection()
