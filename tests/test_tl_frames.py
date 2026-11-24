"""TL notifications captured from a real lamp, and broken ones.

Frames from docs/PROTOCOL.md (btsnoop captures). The RGB status is 21 bytes
long; a 20-byte MTU cuts it inside the trailer, which must still parse.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.light import ColorMode

from custom_components.beurer_daylight_lamps.beurer_daylight_lamps import (
    BeurerInstance,
    is_valid_tl_frame,
)

HEARTBEAT = bytearray.fromhex("feef0c09abbb04d0ff2b550d0a")
WHITE_OFF_100 = bytearray.fromhex("feef0c0dabbb08d00100640078c5550d0a")
RGB_CUT_BY_MTU = bytearray.fromhex("feef0c11abbb0cd0020115007821ff00006c550d")


def _lamp() -> BeurerInstance:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "TL100"
    return BeurerInstance(device)


@pytest.mark.parametrize("frame", [HEARTBEAT, WHITE_OFF_100, RGB_CUT_BY_MTU])
def test_captured_frames_are_valid(frame: bytearray) -> None:
    assert is_valid_tl_frame(frame)


async def test_captured_white_status() -> None:
    lamp = _lamp()
    lamp._light_on = True
    await lamp._handle_notification(MagicMock(), WHITE_OFF_100)
    assert lamp.white_on is False
    assert lamp.is_on is False


async def test_captured_rgb_status_cut_by_mtu() -> None:
    lamp = _lamp()
    await lamp._handle_notification(MagicMock(), RGB_CUT_BY_MTU)
    assert lamp.color_on is True
    assert lamp.color_mode == ColorMode.RGB
    assert lamp.rgb_color == (0x21, 0xFF, 0x00)


def _corrupt(frame: bytearray, index: int) -> bytearray:
    broken = bytearray(frame)
    broken[index] ^= 0xFF
    return broken


@pytest.mark.parametrize(
    "frame",
    [
        _corrupt(WHITE_OFF_100, 9),  # flipped on/off byte: checksum mismatch
        _corrupt(RGB_CUT_BY_MTU, 5),  # not a lamp response (magic AB BB)
        RGB_CUT_BY_MTU[:15],  # first fragment, colour bytes missing
        bytearray(b"\x0a"),  # second fragment
    ],
    ids=["checksum", "magic", "fragment", "tail"],
)
async def test_broken_frames_do_not_change_state(frame: bytearray) -> None:
    lamp = _lamp()
    lamp._light_on = True
    lamp._brightness = 200
    await lamp._handle_notification(MagicMock(), frame)
    assert lamp._light_on is True
    assert lamp._brightness == 200
    assert lamp.color_on is False


async def test_rgb_status_with_short_payload_is_ignored() -> None:
    """A checksum-valid RGB status too short for the colour bytes (IndexError)."""
    from tests.tl_frames import tl_frame

    lamp = _lamp()
    await lamp._handle_notification(MagicMock(), tl_frame([0xD0, 2, 1, 50, 0, 0]))
    assert lamp.color_on is False


async def test_settings_response_is_not_mistaken_for_a_status() -> None:
    """Settings reuse byte 8 (display mode 2 looks like "RGB status")."""
    from tests.tl_frames import tl_frame

    lamp = _lamp()
    # RESP 0xE2: display, date format, time format, feedback, fade (0 = on)
    await lamp._handle_notification(MagicMock(), tl_frame([0xE2, 2, 0, 0, 0, 1]))
    assert lamp.feedback_enabled is True
    assert lamp.fade_enabled is False
