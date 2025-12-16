#!/usr/bin/env python3
"""
Simple BLE command helper for Beurer lamps.

Usage:
    python send_command.py <MAC> <command> [args...]

Examples:
    python send_command.py AA:BB:CC:DD:EE:FF status
    python send_command.py AA:BB:CC:DD:EE:FF on
    python send_command.py AA:BB:CC:DD:EE:FF off
    python send_command.py AA:BB:CC:DD:EE:FF white 50
    python send_command.py AA:BB:CC:DD:EE:FF rgb 255 0 0
    python send_command.py AA:BB:CC:DD:EE:FF effect 2
    python send_command.py AA:BB:CC:DD:EE:FF raw 33 01 1E
    python send_command.py AA:BB:CC:DD:EE:FF timer 30
    python send_command.py AA:BB:CC:DD:EE:FF sunrise 10
"""

import asyncio
import sys
from datetime import datetime

from bleak import BleakClient, BleakScanner

WRITE_UUID = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
READ_UUID = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"

# Known commands
CMD_STATUS = 0x30
CMD_BRIGHTNESS = 0x31
CMD_COLOR = 0x32
CMD_TIMER = 0x33  # Unknown - testing
CMD_EFFECT = 0x34
CMD_OFF = 0x35
CMD_SUNRISE = 0x36  # Unknown - testing
CMD_MODE = 0x37
CMD_UNK_38 = 0x38  # Unknown
CMD_UNK_39 = 0x39  # Unknown

MODE_WHITE = 0x01
MODE_RGB = 0x02


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def checksum(length, data):
    result = length
    for b in data:
        result ^= b
    return result


def packet(payload):
    length = len(payload)
    cs = checksum(length + 2, payload)
    return bytearray(
        [0xFE, 0xEF, 0x0A, length + 7, 0xAB, 0xAA, length + 2]
        + payload
        + [cs, 0x55, 0x0D, 0x0A]
    )


def parse_response(data):
    if len(data) < 10:
        return f"Short response: {data.hex()}"
    
    version = data[8]
    if version == 1:
        on = data[9] == 1
        brightness = data[10] if len(data) > 10 else 0
        return f"WHITE: on={on}, brightness={brightness}%"
    elif version == 2:
        on = data[9] == 1
        brightness = data[10] if len(data) > 10 else 0
        rgb = (data[13], data[14], data[15]) if len(data) > 15 else (0,0,0)
        effect = data[16] if len(data) > 16 else 0
        return f"RGB: on={on}, brightness={brightness}%, rgb={rgb}, effect={effect}"
    elif version == 255:
        return "OFF"
    elif version == 0:
        return "SHUTDOWN"
    else:
        return f"Unknown version {version}: {data.hex()}"


async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    mac = sys.argv[1]
    cmd = sys.argv[2].lower()
    args = sys.argv[3:]
    
    log(f"Scanning for {mac}...")
    device = await BleakScanner.find_device_by_address(mac, timeout=10)
    if not device:
        log("Device not found!")
        sys.exit(1)
    
    log(f"Found: {device.name}")
    
    responses = []
    
    def on_notify(char, data):
        parsed = parse_response(data)
        responses.append(parsed)
        log(f"📥 {data.hex()}")
        log(f"   → {parsed}")
    
    async with BleakClient(device) as client:
        await client.start_notify(READ_UUID, on_notify)
        log("Connected!")
        
        # Build command
        if cmd == "status":
            await client.write_gatt_char(WRITE_UUID, packet([CMD_STATUS, MODE_WHITE]))
            await asyncio.sleep(0.3)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_STATUS, MODE_RGB]))
        
        elif cmd == "on":
            await client.write_gatt_char(WRITE_UUID, packet([CMD_MODE, MODE_WHITE]))
        
        elif cmd == "off":
            await client.write_gatt_char(WRITE_UUID, packet([CMD_OFF, MODE_WHITE]))
            await asyncio.sleep(0.1)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_OFF, MODE_RGB]))
        
        elif cmd == "white" and args:
            brightness = int(args[0])
            await client.write_gatt_char(WRITE_UUID, packet([CMD_MODE, MODE_WHITE]))
            await asyncio.sleep(0.3)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_BRIGHTNESS, MODE_WHITE, brightness]))
        
        elif cmd == "rgb" and len(args) >= 3:
            r, g, b = int(args[0]), int(args[1]), int(args[2])
            await client.write_gatt_char(WRITE_UUID, packet([CMD_MODE, MODE_RGB]))
            await asyncio.sleep(0.3)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_COLOR, r, g, b]))
        
        elif cmd == "effect" and args:
            effect = int(args[0])
            await client.write_gatt_char(WRITE_UUID, packet([CMD_MODE, MODE_RGB]))
            await asyncio.sleep(0.3)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_EFFECT, effect]))
        
        elif cmd == "raw" and args:
            # Send raw bytes: raw 33 01 1E
            payload = [int(x, 16) for x in args]
            log(f"📤 Sending raw: {payload}")
            await client.write_gatt_char(WRITE_UUID, packet(payload))
        
        elif cmd == "timer" and args:
            # Test timer command (0x33)
            minutes = int(args[0])
            log(f"📤 Testing TIMER with {minutes} minutes")
            # Try different formats
            await client.write_gatt_char(WRITE_UUID, packet([CMD_TIMER, minutes]))
            await asyncio.sleep(0.5)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_TIMER, MODE_WHITE, minutes]))
            await asyncio.sleep(0.5)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_TIMER, 0x01, minutes]))
        
        elif cmd == "sunrise" and args:
            # Test sunrise command (0x36)
            duration = int(args[0])
            log(f"📤 Testing SUNRISE with {duration} minutes")
            await client.write_gatt_char(WRITE_UUID, packet([CMD_SUNRISE, duration]))
            await asyncio.sleep(0.5)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_SUNRISE, 0x01, duration]))
            await asyncio.sleep(0.5)
            await client.write_gatt_char(WRITE_UUID, packet([CMD_SUNRISE, 0x02, duration]))
        
        elif cmd == "probe":
            # Test all unknown commands
            log("🔬 Probing unknown commands...")
            for cmd_byte in [0x33, 0x36, 0x38, 0x39]:
                log(f"\n--- Testing 0x{cmd_byte:02X} ---")
                for second in [0x00, 0x01, 0x02, 0x0A, 0x1E, 0x3C]:
                    payload = [cmd_byte, second]
                    log(f"📤 {payload}")
                    await client.write_gatt_char(WRITE_UUID, packet(payload))
                    await asyncio.sleep(0.5)
        
        else:
            log(f"Unknown command: {cmd}")
            print(__doc__)
        
        # Wait for responses
        await asyncio.sleep(1)
        await client.stop_notify(READ_UUID)
    
    log("Done!")


if __name__ == "__main__":
    asyncio.run(main())
