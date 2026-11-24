"""Build TL notifications the way the lamp sends them.

Frame: FE EF 0C len AB BB plen payload[plen - 2] checksum 55 0D 0A, with
checksum = plen XOR payload (see docs/PROTOCOL.md for captured frames).
"""

from __future__ import annotations

# Payload length (byte 6) of the lamp's status notifications
WHITE_STATUS_PLEN = 0x08
RGB_STATUS_PLEN = 0x0C


def tl_frame(payload: bytes | bytearray | list[int]) -> bytearray:
    """Wrap payload bytes (starting with the response command) in a frame."""
    plen = len(payload) + 2
    checksum = plen
    for byte in payload:
        checksum ^= byte
    body = bytearray([0xAB, 0xBB, plen, *payload, checksum, 0x55, 0x0D, 0x0A])
    return bytearray([0xFE, 0xEF, 0x0C, len(body) + 1]) + body


def as_tl_frame(data: bytearray) -> bytearray:
    """Frame a buffer laid out by index (data[6] = plen, payload from data[7]).

    Lets a test set fields at the offsets the handlers read and still send
    a frame that passes the integration's validation.
    """
    plen = data[6]
    payload = bytearray(data[7 : 7 + plen - 2])
    payload.extend(bytes(plen - 2 - len(payload)))
    return tl_frame(payload)
