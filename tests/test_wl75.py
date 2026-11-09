"""Tests for WL75 Wake-up Light support (protocol family 2)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light import ColorMode

from custom_components.beurer_daylight_lamps.const import (
    CMD_WL75_ALARM_WRITE,
    CMD_WL75_LIGHT_BRIGHTNESS,
    CMD_WL75_LIGHT_SWITCH,
    CMD_WL75_MOODLIGHT_SWITCH,
    CMD_WL75_TIME_SYNC,
    RESP_WL75_ALARM,
    RESP_WL75_LIGHT_STATUS,
    RESP_WL75_MOODLIGHT_STATUS,
    RESP_WL75_RADIO_STATUS,
    is_wl75_model,
    is_wl90_model,
    is_wl_model,
)


@pytest.fixture(autouse=True)
def mock_bleak_client():
    """Mock BleakClient for all tests."""
    with patch(
        "custom_components.beurer_daylight_lamps.beurer_daylight_lamps.BleakClient"
    ) as mock:
        yield mock


def _frame(payload: list[int]) -> bytearray:
    """Build a WL75 frame: FE EF plen payload checksum."""
    plen = len(payload) + 1
    checksum = plen
    for byte in payload:
        checksum ^= byte
    return bytearray([0xFE, 0xEF, plen, *payload, checksum])


def _make_instance(name: str = "WL75"):
    from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
        BeurerInstance,
    )

    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = name
    instance = BeurerInstance(device, rssi=-60)
    instance._trigger_update = AsyncMock()
    return instance


def _sent(instance) -> list[list[int]]:
    """Return the messages passed to _send_packet."""
    return [list(c.args[0]) for c in instance._send_packet.call_args_list]


@pytest.mark.parametrize(
    ("name", "wl75", "wl90"),
    [
        ("WL75", True, False),
        ("WL 75 1234", True, False),
        ("WL_75", True, False),
        ("WL90", False, True),
        ("WL 90", False, True),
        ("TL100", False, False),
        (None, False, False),
    ],
)
def test_model_detection(name: str | None, wl75: bool, wl90: bool) -> None:
    """WL75 and WL90 are told apart, both count as WL models."""
    assert is_wl75_model(name) is wl75
    assert is_wl90_model(name) is wl90
    assert is_wl_model(name) is (wl75 or wl90)


def test_wl75_instance_uses_wl75_controller() -> None:
    """A WL75 gets the WL75 controller with two alarm slots."""
    from custom_components.beurer_daylight_lamps.wl75 import WL75Controller

    instance = _make_instance("WL75")
    assert instance.is_wl75
    assert instance.is_wl
    assert not instance.is_wl90
    assert isinstance(instance.wl90, WL75Controller)
    assert len(instance.wl90.alarms) == 2


def test_wl90_instance_keeps_three_alarms() -> None:
    """A WL90 keeps the WL90 controller."""
    from custom_components.beurer_daylight_lamps.wl75 import WL75Controller

    instance = _make_instance("WL90")
    assert instance.is_wl90
    assert not instance.is_wl75
    assert not isinstance(instance.wl90, WL75Controller)
    assert len(instance.wl90.alarms) == 3


@pytest.mark.asyncio
async def test_wl75_packet_framing() -> None:
    """WL75 packets use the short FE EF framing with XOR checksum."""
    instance = _make_instance("WL75")
    instance._write = AsyncMock(return_value=True)
    instance._client = MagicMock(is_connected=True)

    with patch("asyncio.sleep", new=AsyncMock()):
        await instance._send_packet([CMD_WL75_LIGHT_SWITCH, 1])

    instance._write.assert_awaited_once()
    packet = instance._write.call_args.args[0]
    assert packet == _frame([CMD_WL75_LIGHT_SWITCH, 1])
    assert packet == bytearray([0xFE, 0xEF, 0x03, 0x12, 0x01, 0x10])


@pytest.mark.asyncio
async def test_tl100_packet_framing_unchanged() -> None:
    """TL100 framing is untouched by WL75 support."""
    instance = _make_instance("TL100")
    instance._write = AsyncMock(return_value=True)
    instance._client = MagicMock(is_connected=True)

    with patch("asyncio.sleep", new=AsyncMock()):
        await instance._send_packet([0x37, 0x01])

    packet = instance._write.call_args.args[0]
    assert packet[:3] == bytearray([0xFE, 0xEF, 0x0A])
    assert packet[-3:] == bytearray([0x55, 0x0D, 0x0A])


@pytest.mark.asyncio
async def test_white_light_status_notification() -> None:
    """A white light status switches the instance to native white."""
    instance = _make_instance("WL75")
    data = _frame([RESP_WL75_LIGHT_STATUS, 1, 50, 1, 15])

    await instance._handle_notification(MagicMock(), data)

    assert instance.color_mode == ColorMode.WHITE
    assert instance.white_on
    assert not instance.color_on
    assert instance.white_brightness == int(50 / 100 * 255)
    assert instance.timer_active
    assert instance.timer_minutes == 15
    assert instance.available
    instance._trigger_update.assert_awaited()


@pytest.mark.asyncio
async def test_moodlight_status_notification() -> None:
    """A mood light status switches the instance to RGB with color and scene."""
    instance = _make_instance("WL75")
    data = _frame([RESP_WL75_MOODLIGHT_STATUS, 1, 100, 0, 0, 10, 20, 30, 0])

    await instance._handle_notification(MagicMock(), data)

    assert instance.color_mode == ColorMode.RGB
    assert instance.color_on
    assert not instance.white_on
    assert instance.rgb_color == (10, 20, 30)
    assert instance.color_brightness == 255
    assert instance.effect == "Off"
    assert not instance.timer_active


@pytest.mark.asyncio
async def test_bad_checksum_is_ignored() -> None:
    """A frame with a wrong checksum does not change state."""
    instance = _make_instance("WL75")
    data = _frame([RESP_WL75_LIGHT_STATUS, 1, 50, 0, 0])
    data[-1] ^= 0xFF

    await instance._handle_notification(MagicMock(), data)

    assert not instance.white_on
    instance._trigger_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_radio_status_delegated_to_controller() -> None:
    """Radio status frames are parsed by the WL75 controller."""
    instance = _make_instance("WL75")
    # on, channel 3, 101.5 MHz (1015), volume 7, timer on, 30 min
    data = _frame([RESP_WL75_RADIO_STATUS, 1, 3, 0x03, 0xF7, 7, 1, 30])

    await instance._handle_notification(MagicMock(), data)

    radio = instance.wl90.radio
    assert radio.is_on
    assert radio.channel == 2
    assert radio.frequency == 1015
    assert radio.volume == 7
    assert radio.sleep_timer_on
    assert radio.sleep_timer_minutes == 30


@pytest.mark.asyncio
async def test_alarm_response_parsed() -> None:
    """Alarm info frames fill the matching slot."""
    instance = _make_instance("WL75")
    # slot 2, 06:30, enabled + Mon-Fri, tone 2, vol 5, snooze idx 2, wake, sunrise
    data = _frame([RESP_WL75_ALARM, 2, 30, 6, 0x80 | 0x1F, 2, 5, 2, 0, 20, 80])

    await instance._handle_notification(MagicMock(), data)

    alarm = instance.wl90.alarms[1]
    assert (alarm.hour, alarm.minute) == (6, 30)
    assert alarm.enabled
    assert alarm.days == 0x1F
    assert alarm.tone == 2
    assert alarm.volume == 5
    assert alarm.sunrise_time == 20
    assert alarm.sunrise_brightness == 80
    assert alarm.sunrise_enabled


@pytest.mark.asyncio
async def test_sync_alarm_packet() -> None:
    """Alarm writes use the WL75 opcode and 1-based slot id."""
    instance = _make_instance("WL75")
    instance._send_packet = AsyncMock(return_value=True)
    alarm = instance.wl90.alarms[0]
    alarm.enabled = True
    alarm.hour = 7
    alarm.minute = 15

    assert await instance.wl90.sync_alarm(0, alarm)

    msg = _sent(instance)[0]
    assert msg[:5] == [CMD_WL75_ALARM_WRITE, 1, 15, 7, 0x80 | (alarm.days & 0x7F)]


@pytest.mark.asyncio
async def test_sync_alarm_rejects_third_slot() -> None:
    """The WL75 has only two alarm slots."""
    instance = _make_instance("WL75")
    instance._send_packet = AsyncMock(return_value=True)

    assert not await instance.wl90.sync_alarm(2)
    instance._send_packet.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_white_uses_wl75_commands() -> None:
    """set_white switches the mood light off and the white light on."""
    instance = _make_instance("WL75")
    instance._send_packet = AsyncMock(return_value=True)
    instance._color_on = True

    with patch("asyncio.sleep", new=AsyncMock()):
        await instance.set_white(2)

    sent = _sent(instance)
    assert [CMD_WL75_MOODLIGHT_SWITCH, 0] in sent
    assert [CMD_WL75_LIGHT_SWITCH, 1] in sent
    # Low HA brightness is not floored to 0 % (issue #8)
    assert [CMD_WL75_LIGHT_BRIGHTNESS, 1] in sent
    assert instance.white_on
    assert not instance.color_on


@pytest.mark.asyncio
async def test_turn_off_switches_both_lights_off() -> None:
    """turn_off sends off for white and mood light."""
    instance = _make_instance("WL75")
    instance._send_packet = AsyncMock(return_value=True)
    instance._light_on = True

    with patch("asyncio.sleep", new=AsyncMock()):
        await instance.turn_off()

    sent = _sent(instance)
    assert [CMD_WL75_LIGHT_SWITCH, 0] in sent
    assert [CMD_WL75_MOODLIGHT_SWITCH, 0] in sent
    assert not instance.white_on
    assert not instance.color_on


@pytest.mark.asyncio
async def test_sync_time_wl75_packet() -> None:
    """WL75 time sync has no weekday byte and records the sync time."""
    instance = _make_instance("WL75")
    instance._send_packet = AsyncMock(return_value=True)

    with patch("asyncio.sleep", new=AsyncMock()):
        assert await instance.sync_time()

    msg = _sent(instance)[0]
    assert msg[0] == CMD_WL75_TIME_SYNC
    assert len(msg) == 7
    assert instance.last_time_sync is not None


@pytest.mark.asyncio
async def test_fade_not_supported_on_wl75() -> None:
    """The fade hardware setting does not exist on the WL75."""
    instance = _make_instance("WL75")
    instance._send_packet = AsyncMock(return_value=True)

    assert not await instance.set_fade(True)
    instance._send_packet.assert_not_awaited()


@pytest.mark.asyncio
async def test_switch_setup_for_wl75() -> None:
    """WL75: no fade switch, one switch per alarm slot."""
    from custom_components.beurer_daylight_lamps.switch import (
        BeurerAlarmSwitch,
        BeurerDeviceSwitch,
        async_setup_entry,
    )

    instance = _make_instance("WL75")
    coordinator = MagicMock()
    coordinator.instance = instance
    entry = MagicMock()
    entry.runtime_data.coordinator = coordinator
    entry.runtime_data.instance = instance
    entry.data = {"name": "WL75"}
    entry.entry_id = "entry_wl75"

    added: list = []
    await async_setup_entry(MagicMock(), entry, added.extend)

    device_keys = [
        e.entity_description.key for e in added if isinstance(e, BeurerDeviceSwitch)
    ]
    assert "fade" not in device_keys
    assert "feedback_sound" in device_keys or "feedback" in device_keys
    assert len([e for e in added if isinstance(e, BeurerAlarmSwitch)]) == 2


@pytest.mark.asyncio
async def test_media_player_setup_for_wl75() -> None:
    """WL75 has an FM radio but no Bluetooth speaker."""
    from custom_components.beurer_daylight_lamps.media_player import (
        BeurerMusicPlayer,
        BeurerRadioPlayer,
        async_setup_entry,
    )

    instance = _make_instance("WL75")
    coordinator = MagicMock()
    coordinator.instance = instance
    entry = MagicMock()
    entry.runtime_data.coordinator = coordinator
    entry.runtime_data.instance = instance
    entry.data = {"name": "WL75"}

    added: list = []
    await async_setup_entry(MagicMock(), entry, added.extend)

    assert any(isinstance(e, BeurerRadioPlayer) for e in added)
    assert not any(isinstance(e, BeurerMusicPlayer) for e in added)
