#!/usr/bin/env python3
"""
BLE Protocol Sniffer for Beurer Daylight Lamps.

This tool helps reverse engineer the BLE protocol by:
1. Connecting to the lamp
2. Logging all sent commands and received notifications
3. Allowing manual command injection to discover new protocol features

Usage:
    python ble_sniffer.py <MAC_ADDRESS>

Example:
    python ble_sniffer.py AA:BB:CC:DD:EE:FF

Requirements:
    pip install bleak

Protocol Documentation (Known):
    Header: [0xFE, 0xEF, 0x0A, length, 0xAB, 0xAA, payload_len]
    Trailer: [checksum, 0x55, 0x0D, 0x0A]

    Commands (first byte of payload):
    - 0x30: Request status (MODE_WHITE=0x01, MODE_RGB=0x02)
    - 0x31: Set brightness (mode, brightness_percent)
    - 0x32: Set RGB color (r, g, b)
    - 0x34: Set effect (effect_index)
    - 0x35: Turn off (mode)
    - 0x37: Set mode (MODE_WHITE=0x01, MODE_RGB=0x02)

    Unknown commands to investigate:
    - 0x33: Possibly timer related?
    - 0x36: Possibly sunrise/sunset?
    - 0x38: Unknown
    - 0x39: Unknown
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError

# BLE UUIDs
WRITE_UUID = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
READ_UUID = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"

# Known protocol constants
CMD_STATUS = 0x30
CMD_BRIGHTNESS = 0x31
CMD_COLOR = 0x32
CMD_UNKNOWN_33 = 0x33  # Timer?
CMD_EFFECT = 0x34
CMD_OFF = 0x35
CMD_UNKNOWN_36 = 0x36  # Sunrise/Sunset?
CMD_MODE = 0x37
CMD_UNKNOWN_38 = 0x38
CMD_UNKNOWN_39 = 0x39

MODE_WHITE = 0x01
MODE_RGB = 0x02


def log(msg: str) -> None:
    """Print timestamped log message."""
    ts = datetime.now(tz=UTC).strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def calculate_checksum(length: int, data: list[int]) -> int:
    """Calculate packet checksum."""
    result = length
    for byte in data:
        result ^= byte
    return result


def build_packet(message: list[int]) -> bytearray:
    """Build a complete BLE packet from a command message."""
    length = len(message)
    checksum = calculate_checksum(length + 2, message)
    return bytearray(
        [
            0xFE,
            0xEF,
            0x0A,
            length + 7,
            0xAB,
            0xAA,
            length + 2,
            *message,
            checksum,
            0x55,
            0x0D,
            0x0A,
        ]
    )


def parse_notification(data: bytearray) -> dict:
    """Parse a notification response."""
    result = {
        "raw": data.hex(),
        "length": len(data),
    }

    if len(data) >= 10:
        result["version"] = data[8]

        if data[8] == 1:  # White mode
            result["mode"] = "WHITE"
            result["on"] = data[9] == 1
            if len(data) > 10:
                result["brightness"] = data[10]

        elif data[8] == 2:  # RGB mode
            result["mode"] = "RGB"
            result["on"] = data[9] == 1
            if len(data) > 16:
                result["brightness"] = data[10]
                result["rgb"] = (data[13], data[14], data[15])
                result["effect"] = data[16]

        elif data[8] == 255:
            result["mode"] = "OFF"

        elif data[8] == 0:
            result["mode"] = "SHUTDOWN"

    return result


class BLESniffer:
    """BLE Protocol Sniffer for Beurer lamps."""

    def __init__(self, mac: str):
        self.mac = mac
        self.client = None
        self.log_file = None

    def _notification_handler(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle incoming BLE notifications."""
        parsed = parse_notification(data)
        log(f"📥 RECV: {data.hex()}")
        log(f"   Parsed: {parsed}")

        if self.log_file:
            self.log_file.write(
                f"RECV,{datetime.now(tz=UTC).isoformat()},{data.hex()},{parsed}\n"
            )
            self.log_file.flush()

    async def send_raw(self, data: list[int], description: str = "") -> None:
        """Send raw bytes to the device."""
        packet = build_packet(data)
        log(f"📤 SEND: {packet.hex()} ({description or 'raw'})")
        log(f"   Payload: {data}")

        if self.log_file:
            self.log_file.write(
                f"SEND,{datetime.now(tz=UTC).isoformat()},{packet.hex()},{data},{description}\n"
            )
            self.log_file.flush()

        await self.client.write_gatt_char(WRITE_UUID, packet)
        await asyncio.sleep(0.3)

    async def connect(self) -> bool:
        """Connect to the device."""
        log(f"🔍 Scanning for {self.mac}...")

        device = await BleakScanner.find_device_by_address(self.mac, timeout=10)
        if not device:
            log("❌ Device not found!")
            return False

        log(f"✅ Found: {device.name} ({device.address})")

        self.client = BleakClient(device)
        await self.client.connect()
        log("✅ Connected!")

        # Start notifications
        await self.client.start_notify(READ_UUID, self._notification_handler)
        log("✅ Notifications enabled")

        return True

    async def disconnect(self) -> None:
        """Disconnect from device."""
        if self.client and self.client.is_connected:
            await self.client.stop_notify(READ_UUID)
            await self.client.disconnect()
            log("👋 Disconnected")

    async def _handle_command(self, parts: list[str]) -> bool:
        """Handle a single interactive command. Returns False to quit."""
        handlers = {
            "status": self._cmd_status,
            "on": self._cmd_on,
            "off": self._cmd_off,
            "white": self._cmd_white,
            "rgb": self._cmd_rgb,
            "effect": self._cmd_effect,
            "raw": self._cmd_raw,
            "probe": self._cmd_probe,
        }

        if parts[0] in ("quit", "q"):
            return False

        handler = handlers.get(parts[0])
        if handler:
            await handler(parts)
        else:
            print(f"Unknown command: {' '.join(parts)}")
        return True

    async def _cmd_status(self, _parts: list[str]) -> None:
        await self.send_raw([CMD_STATUS, MODE_WHITE], "status white")
        await self.send_raw([CMD_STATUS, MODE_RGB], "status rgb")

    async def _cmd_on(self, _parts: list[str]) -> None:
        await self.send_raw([CMD_MODE, MODE_WHITE], "on white")

    async def _cmd_off(self, _parts: list[str]) -> None:
        await self.send_raw([CMD_OFF, MODE_WHITE], "off white")
        await self.send_raw([CMD_OFF, MODE_RGB], "off rgb")

    async def _cmd_white(self, parts: list[str]) -> None:
        if len(parts) < 2:
            print("Usage: white <0-100>")
            return
        brightness = int(parts[1])
        await self.send_raw([CMD_MODE, MODE_WHITE], "mode white")
        await self.send_raw(
            [CMD_BRIGHTNESS, MODE_WHITE, brightness], f"brightness {brightness}%"
        )

    async def _cmd_rgb(self, parts: list[str]) -> None:
        if len(parts) < 4:
            print("Usage: rgb <r> <g> <b>")
            return
        r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
        await self.send_raw([CMD_MODE, MODE_RGB], "mode rgb")
        await self.send_raw([CMD_COLOR, r, g, b], f"color ({r},{g},{b})")

    async def _cmd_effect(self, parts: list[str]) -> None:
        if len(parts) < 2:
            print("Usage: effect <0-10>")
            return
        effect = int(parts[1])
        await self.send_raw([CMD_MODE, MODE_RGB], "mode rgb")
        await self.send_raw([CMD_EFFECT, effect], f"effect {effect}")

    async def _cmd_raw(self, parts: list[str]) -> None:
        hex_bytes = [int(x, 16) for x in parts[1:]]
        await self.send_raw(hex_bytes, "manual raw")

    async def _cmd_probe(self, _parts: list[str]) -> None:
        print("\n🔬 Probing unknown commands...")
        for cmd_byte in [0x33, 0x36, 0x38, 0x39]:
            print(f"\n--- Testing 0x{cmd_byte:02X} ---")
            for second in [0x00, 0x01, 0x02, 0x0A, 0x1E, 0x3C]:
                await self.send_raw(
                    [cmd_byte, second], f"probe 0x{cmd_byte:02X} 0x{second:02X}"
                )
                await asyncio.sleep(0.5)

    async def interactive_mode(self) -> None:
        """Run interactive command mode."""
        print("\n" + "=" * 60)
        print("BLE Protocol Sniffer - Interactive Mode")
        print("=" * 60)
        print("Commands:")
        print("  status      - Request current status")
        print("  on          - Turn on (white mode)")
        print("  off         - Turn off")
        print("  white <0-100> - Set white brightness")
        print("  rgb <r> <g> <b> - Set RGB color")
        print("  effect <0-10> - Set effect")
        print("  raw <hex>   - Send raw hex bytes (e.g., 'raw 33 01')")
        print("  probe       - Try unknown commands 0x33-0x39")
        print("  quit        - Exit")
        print("=" * 60 + "\n")

        while True:
            try:
                cmd = input(">>> ").strip().lower()
            except EOFError:
                break

            if not cmd:
                continue

            try:
                if not await self._handle_command(cmd.split()):
                    break
            except (BleakError, TimeoutError, OSError, ValueError) as e:
                print(f"Error: {e}")


def _open_log_file(mac: str):
    """Open a CSV log file for the session (sync helper for async main)."""
    log_filename = f"ble_log_{mac.replace(':', '')}_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    log_path = Path(log_filename)
    log_file = log_path.open("w")
    log_file.write("direction,timestamp,raw_hex,parsed,description\n")
    log(f"📝 Logging to {log_filename}")
    return log_file


async def main():
    if len(sys.argv) < 2:
        print("Usage: python ble_sniffer.py <MAC_ADDRESS>")
        print("Example: python ble_sniffer.py AA:BB:CC:DD:EE:FF")
        sys.exit(1)

    mac = sys.argv[1]
    sniffer = BLESniffer(mac)
    sniffer.log_file = _open_log_file(mac)

    try:
        if await sniffer.connect():
            await sniffer.interactive_mode()
    finally:
        await sniffer.disconnect()
        if sniffer.log_file:
            sniffer.log_file.close()


if __name__ == "__main__":
    asyncio.run(main())
