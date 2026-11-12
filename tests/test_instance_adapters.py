"""Adapter selection of BeurerInstance (GATT-capable sources, cooldowns)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.beurer_daylight_lamps import beurer_daylight_lamps as mod
from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)

BT = "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.bluetooth"


def make_instance(hass: object | None = None) -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "TL100"
    return BeurerInstance(device, rssi=-60, hass=hass)  # type: ignore[arg-type]


def scanner_device(source: str, rssi: int | None) -> MagicMock:
    dev = MagicMock()
    dev.scanner.source = source
    dev.advertisement.rssi = rssi
    dev.ble_device = MagicMock(name=f"ble-{source}")
    return dev


@pytest.mark.parametrize(
    ("source", "capable"),
    [
        ("ShellyPlugS-1234", False),
        ("living_room_btproxy", True),
        ("esp-proxy", True),
        ("hci0", True),
        ("bcm43438", True),
        ("BRCM-chip", True),
        ("something-else", True),
    ],
)
def test_gatt_capable_source(source: str, capable: bool) -> None:
    assert make_instance()._is_gatt_capable_source(source) is capable


def test_cooldown_lifecycle() -> None:
    inst = make_instance()
    assert not inst._is_adapter_in_cooldown("hci0")
    inst._mark_adapter_failed("hci0")
    assert inst._is_adapter_in_cooldown("hci0")
    inst._adapter_failures["hci0"] = 0  # long ago
    assert not inst._is_adapter_in_cooldown("hci0")
    assert "hci0" not in inst._adapter_failures
    inst._mark_adapter_failed("proxy")
    inst._clear_adapter_failure("proxy")
    inst._clear_adapter_failure("never-failed")
    assert inst._adapter_failures == {}


class TestGattCapableDevice:
    """Picking a device from the scanners that see the lamp."""

    def test_without_hass(self) -> None:
        inst = make_instance()
        assert inst._get_gatt_capable_device() is inst._ble_device

    def test_best_rssi_wins(self) -> None:
        inst = make_instance(MagicMock())
        near = scanner_device("kitchen_btproxy", -50)
        far = scanner_device("hci0", -80)
        shelly = scanner_device("shelly1", -30)
        failed = scanner_device("bedroom_proxy", -40)
        inst._mark_adapter_failed("bedroom_proxy")
        with patch(
            f"{BT}.async_scanner_devices_by_address",
            return_value=[far, near, shelly, failed],
        ):
            assert inst._get_gatt_capable_device() is near.ble_device

    def test_cooldown_used_as_last_resort(self) -> None:
        inst = make_instance(MagicMock())
        a = scanner_device("hci0", None)
        b = scanner_device("proxy", -70)
        inst._mark_adapter_failed("hci0")
        inst._mark_adapter_failed("proxy")
        with patch(f"{BT}.async_scanner_devices_by_address", return_value=[a, b]):
            assert inst._get_gatt_capable_device() is b.ble_device

    def test_only_passive_scanners(self, caplog: pytest.LogCaptureFixture) -> None:
        inst = make_instance(MagicMock())
        fallback = object()
        with (
            patch(
                f"{BT}.async_scanner_devices_by_address",
                return_value=[scanner_device("shellyplug", -40)],
            ),
            patch(f"{BT}.async_ble_device_from_address", return_value=fallback),
        ):
            assert inst._get_gatt_capable_device() is fallback
        assert "Only passive scanners" in caplog.text


class TestSelectBestAdapter:
    """_select_best_adapter."""

    def test_without_hass(self) -> None:
        inst = make_instance()
        before = inst._ble_device
        inst._select_best_adapter()
        assert inst._ble_device is before

    def test_gatt_device_and_rssi(self) -> None:
        inst = make_instance(MagicMock())
        fresh = MagicMock()
        with (
            patch.object(inst, "_get_gatt_capable_device", return_value=fresh),
            patch(f"{BT}.async_last_service_info", return_value=MagicMock(rssi=-42)),
        ):
            inst._select_best_adapter()
        assert inst._ble_device is fresh
        assert inst.rssi == -42

    def test_gatt_device_without_service_info(self) -> None:
        inst = make_instance(MagicMock())
        fresh = MagicMock()
        with (
            patch.object(inst, "_get_gatt_capable_device", return_value=fresh),
            patch(f"{BT}.async_last_service_info", return_value=None),
        ):
            inst._select_best_adapter()
        assert inst._ble_device is fresh
        assert inst.rssi == -60

    def test_non_connectable_fallback(self) -> None:
        inst = make_instance(MagicMock())
        passive = MagicMock()
        with (
            patch.object(inst, "_get_gatt_capable_device", return_value=None),
            patch(f"{BT}.async_ble_device_from_address", return_value=passive),
        ):
            inst._select_best_adapter()
        assert inst._ble_device is passive

    def test_keeps_cached_device(self) -> None:
        inst = make_instance(MagicMock())
        cached = inst._ble_device
        with (
            patch.object(inst, "_get_gatt_capable_device", return_value=None),
            patch(f"{BT}.async_ble_device_from_address", return_value=None),
        ):
            inst._select_best_adapter()
        assert inst._ble_device is cached


def test_cooldown_constant_positive() -> None:
    assert mod.ADAPTER_FAILURE_COOLDOWN > 0
