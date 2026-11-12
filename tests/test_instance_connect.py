"""connect(), post-connect setup and repair issues of BeurerInstance."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakAbortedError,
    BleakConnectionError,
    BleakNotFoundError,
    BleakOutOfConnectionSlotsError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import pytest

from custom_components.beurer_daylight_lamps import beurer_daylight_lamps as mod
from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
)
from custom_components.beurer_daylight_lamps.const import (
    CMD_DEVICE_PERMISSION,
    CMD_SETTINGS_READ,
    CMD_WL75_PERMISSION,
    DOMAIN,
    READ_CHARACTERISTIC_UUID,
    WRITE_CHARACTERISTIC_UUID,
)

M = "custom_components.beurer_daylight_lamps.beurer_daylight_lamps"


@pytest.fixture(autouse=True)
def no_sleep():
    with patch(f"{M}.asyncio.sleep", new=AsyncMock()):
        yield


def make_instance(name: str = "TL100", hass=None) -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    return BeurerInstance(device, rssi=-60, hass=hass)


def gatt_client(uuids=(READ_CHARACTERISTIC_UUID, WRITE_CHARACTERISTIC_UUID)):
    client = MagicMock()
    client.is_connected = True
    service = MagicMock()
    service.characteristics = [MagicMock(uuid=u) for u in uuids]
    client.services = [service]
    client.start_notify = AsyncMock()
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    return client


class TestSetupAfterConnect:
    """Characteristic discovery and the initial command sequence."""

    async def test_no_client(self) -> None:
        assert not await make_instance()._setup_after_connect()

    async def test_missing_characteristics(self) -> None:
        inst = make_instance()
        inst._client = gatt_client(uuids=(READ_CHARACTERISTIC_UUID,))
        inst.disconnect = AsyncMock()
        assert not await inst._setup_after_connect()
        inst.disconnect.assert_awaited_once()

    async def _run(self, inst: BeurerInstance) -> list[list[int]]:
        inst._send_packet = AsyncMock(return_value=True)
        inst._request_status = AsyncMock()
        inst.sync_time = AsyncMock(return_value=True)
        inst.query_settings = AsyncMock(return_value=True)
        inst._trigger_update = AsyncMock()
        assert await inst._setup_after_connect()
        assert inst._available
        inst._trigger_update.assert_awaited_once()
        return [c.args[0] for c in inst._send_packet.await_args_list]

    async def test_tl_sequence(self) -> None:
        inst = make_instance()
        inst._client = gatt_client()
        packets = await self._run(inst)
        assert packets == [[CMD_DEVICE_PERMISSION], [CMD_SETTINGS_READ]]
        inst.sync_time.assert_awaited_once()

    async def test_tl_settings_known(self) -> None:
        inst = make_instance()
        inst._client = gatt_client()
        inst._feedback_enabled = True
        assert await self._run(inst) == [[CMD_DEVICE_PERMISSION]]

    async def test_wl90_queries_alarms_radio_music(self) -> None:
        inst = make_instance("WL90_1234")
        inst._client = gatt_client()
        packets = await self._run(inst)
        assert len(packets) == 2 + 3 + 2

    async def test_wl75_sequence(self) -> None:
        inst = make_instance("WL75_1234")
        inst._client = gatt_client()
        inst._wl90.query_radio_status = AsyncMock(return_value=True)
        packets = await self._run(inst)
        assert packets[0] == [CMD_WL75_PERMISSION, 0x75]
        assert len(packets) == 3  # permission + two alarm reads
        inst.query_settings.assert_awaited_once()
        inst._wl90.query_radio_status.assert_awaited_once()

    async def test_notify_falls_back_without_bluez_kwarg(self) -> None:
        inst = make_instance()
        client = gatt_client()
        client.start_notify = AsyncMock(side_effect=[TypeError, None])
        inst._client = client
        await self._run(inst)
        assert client.start_notify.await_count == 2

    async def test_notify_retries_transient_abort(self) -> None:
        inst = make_instance()
        client = gatt_client()
        client.start_notify = AsyncMock(
            side_effect=[BleakError("BluetoothGATTNotifyResponse lost"), None]
        )
        inst._client = client
        await self._run(inst)
        assert client.start_notify.await_count == 2

    async def test_notify_other_error_raises(self) -> None:
        inst = make_instance()
        client = gatt_client()
        client.start_notify = AsyncMock(side_effect=BleakError("nope"))
        inst._client = client
        with pytest.raises(BleakError):
            await inst._setup_after_connect()


class TestConnect:
    """connect() outcomes."""

    async def test_already_connected(self) -> None:
        inst = make_instance()
        inst._client = gatt_client()
        with patch(f"{M}.establish_connection") as est:
            assert await inst.connect()
        est.assert_not_called()

    async def test_success_tracks_reconnects(self, hass: HomeAssistant) -> None:
        inst = make_instance(hass=hass)
        client = gatt_client()
        inst._connection_start_time = 1.0  # a previous connection existed
        inst._mark_adapter_failed("proxy")
        with (
            patch(f"{M}.establish_connection", new=AsyncMock(return_value=client)),
            patch.object(inst, "_select_best_adapter"),
            patch.object(inst, "_setup_after_connect", new=AsyncMock(return_value=True)),
            patch.object(inst, "_start_watchdog") as watchdog,
            patch(
                f"{M}.bluetooth.async_last_service_info",
                return_value=MagicMock(source="proxy"),
            ),
        ):
            assert await inst.connect()
        assert inst._client is client
        assert inst.reconnect_count == 1
        assert inst._ever_connected
        assert "proxy" not in inst._adapter_failures
        watchdog.assert_called_once()

    async def test_fresh_device_callback(self, hass: HomeAssistant) -> None:
        inst = make_instance(hass=hass)
        fresh = MagicMock()
        fresh.name = "other-adapter"
        captured = {}

        async def fake_establish(*args, **kwargs):
            captured["cb"] = kwargs["ble_device_callback"]
            raise BleakNotFoundError("gone")

        with (
            patch(f"{M}.establish_connection", new=fake_establish),
            patch.object(inst, "_select_best_adapter"),
            patch.object(inst, "_get_gatt_capable_device", return_value=fresh),
            patch(f"{M}.bluetooth.async_last_service_info", return_value=None),
        ):
            assert not await inst.connect()
            assert captured["cb"]() is fresh
            assert inst._ble_device is fresh
        inst._hass = None
        assert captured["cb"]() is fresh

    async def test_setup_failure(self) -> None:
        inst = make_instance()
        with (
            patch(f"{M}.establish_connection", new=AsyncMock(return_value=gatt_client())),
            patch.object(inst, "_setup_after_connect", new=AsyncMock(return_value=False)),
        ):
            assert not await inst.connect()

    @pytest.mark.parametrize(
        "error",
        [
            BleakNotFoundError("not found"),
            BleakAbortedError("aborted"),
            BleakConnectionError("failed"),
            BleakError("changed connection status while waiting"),
            TimeoutError("slow"),
        ],
    )
    async def test_errors_mark_adapter(
        self, hass: HomeAssistant, error: Exception
    ) -> None:
        inst = make_instance(hass=hass)
        inst.disconnect = AsyncMock()
        with (
            patch(f"{M}.establish_connection", new=AsyncMock(side_effect=error)),
            patch.object(inst, "_select_best_adapter"),
            patch(
                f"{M}.bluetooth.async_last_service_info",
                return_value=MagicMock(source="hci0"),
            ),
        ):
            assert not await inst.connect()
        assert "hci0" in inst._adapter_failures
        inst.disconnect.assert_awaited_once()

    async def test_out_of_slots_raises_issue(self, hass: HomeAssistant) -> None:
        inst = make_instance(hass=hass)
        inst.disconnect = AsyncMock()
        issues = ir.async_get(hass)
        with (
            patch(
                f"{M}.establish_connection",
                new=AsyncMock(side_effect=BleakOutOfConnectionSlotsError("full")),
            ),
            patch.object(inst, "_select_best_adapter"),
            patch(f"{M}.bluetooth.async_last_service_info", return_value=None),
        ):
            assert not await inst.connect()
        assert issues.async_get_issue(DOMAIN, "adapter_full_aabbccddeeff")
        with (
            patch(f"{M}.establish_connection", new=AsyncMock(return_value=gatt_client())),
            patch.object(inst, "_select_best_adapter"),
            patch.object(inst, "_setup_after_connect", new=AsyncMock(return_value=True)),
            patch.object(inst, "_start_watchdog"),
            patch(f"{M}.bluetooth.async_last_service_info", return_value=None),
        ):
            inst._client = None
            assert await inst.connect()
        assert issues.async_get_issue(DOMAIN, "adapter_full_aabbccddeeff") is None

    def test_issue_helpers_without_hass(self) -> None:
        inst = make_instance()
        inst._raise_adapter_full_issue(BleakOutOfConnectionSlotsError("x"))
        inst._clear_adapter_full_issue()
        inst._update_signal_issue()
        assert inst._device_display_name() == "AA:BB:CC:DD:EE:FF"


class TestSignalIssue:
    """Weak-connection repair issue."""

    async def test_raise_and_clear(self, hass: HomeAssistant) -> None:
        inst = make_instance(hass=hass)
        issues = ir.async_get(hass)
        issue_id = inst._weak_connection_issue_id()
        with patch.object(
            inst._signal_health, "problem", return_value=mod.PROBLEM_WEAK_SIGNAL
        ):
            inst._update_signal_issue()
            inst._update_signal_issue()  # unchanged: no-op
        issue = issues.async_get_issue(DOMAIN, issue_id)
        assert issue.translation_key == "weak_signal"
        with patch.object(inst._signal_health, "problem", return_value="reconnects"):
            inst._update_signal_issue()
        assert issues.async_get_issue(DOMAIN, issue_id).translation_key == (
            "frequent_reconnects"
        )
        with patch.object(inst._signal_health, "problem", return_value=None):
            inst._update_signal_issue()
        assert issues.async_get_issue(DOMAIN, issue_id) is None

    async def test_shutdown_clears_issue(self, hass: HomeAssistant) -> None:
        inst = make_instance(hass=hass)
        with patch.object(
            inst._signal_health, "problem", return_value=mod.PROBLEM_WEAK_SIGNAL
        ):
            inst._update_signal_issue()
        await inst.shutdown()
        assert inst._closing
        assert (
            ir.async_get(hass).async_get_issue(DOMAIN, inst._weak_connection_issue_id())
            is None
        )

    async def test_display_name_from_registry(self, hass: HomeAssistant) -> None:
        from homeassistant.helpers import device_registry as dr
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")},
            name="Bedroom lamp",
        )
        assert make_instance(hass=hass)._device_display_name() == "Bedroom lamp"


class TestUpdateAndDisconnect:
    """update() and disconnect() error handling."""

    async def test_update_cannot_connect(self) -> None:
        inst = make_instance()
        inst.connect = AsyncMock(return_value=False)
        inst._request_status = AsyncMock()
        await inst.update()
        inst._request_status.assert_not_awaited()

    @pytest.mark.parametrize("error", [BleakError("x"), TimeoutError(), OSError()])
    async def test_update_errors_disconnect(self, error: Exception) -> None:
        inst = make_instance()
        inst._client = gatt_client()
        inst._request_status = AsyncMock(side_effect=error)
        inst.disconnect = AsyncMock()
        await inst.update()
        inst.disconnect.assert_awaited_once()

    @pytest.mark.parametrize("error", [BleakError("x"), TimeoutError(), OSError()])
    async def test_disconnect_swallows_errors(self, error: Exception) -> None:
        inst = make_instance()
        client = gatt_client()
        client.stop_notify = AsyncMock(side_effect=error)
        client.disconnect = AsyncMock(side_effect=error)
        inst._client = client
        inst._read_uuid = READ_CHARACTERISTIC_UUID
        inst._available = True
        await inst.disconnect()
        assert not inst._available
