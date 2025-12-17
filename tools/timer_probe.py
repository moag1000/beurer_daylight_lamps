#!/usr/bin/env python3
"""Probe timer commands for Beurer TL100."""

import requests
import time
import sys

HA_URL = "http://192.168.2.99:8123"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI4NTljYjkwYThhZmQ0Y2Y4OGY5ZGUyOTQ0YTY3MjNmNiIsImlhdCI6MTc2NTk4NTMwOCwiZXhwIjoyMDgxMzQ1MzA4fQ.RbNNifJSwpqjnB1-DHPT6I9SMLl0g_yoY_Vrg4SCLAE"
DEVICE_ID = "757db7b50ca2d8708f5c50aee0973c16"

HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json"
}

def send_raw_cmd(cmd: str) -> bool:
    """Send raw BLE command."""
    try:
        r = requests.post(
            f"{HA_URL}/api/services/beurer_daylight_lamps/send_raw_command",
            headers=HEADERS,
            json={"device_id": DEVICE_ID, "command": cmd},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending {cmd}: {e}")
        return False

def get_last_notifications(n: int = 5) -> list:
    """Get last N real notifications (not 0a)."""
    try:
        r = requests.get(
            f"{HA_URL}/api/history/period?filter_entity_id=sensor.tl100_f33d_last_raw_notification",
            headers=HEADERS,
            timeout=10
        )
        data = r.json()
        if data and len(data) > 0:
            notifications = []
            for entry in data[0]:
                state = entry.get("state", "")
                if state.startswith("feef0c") and len(state) > 20:
                    notifications.append(state)
            return notifications[-n:]
    except Exception as e:
        print(f"Error getting notifications: {e}")
    return []

def parse_rgb_notification(hex_str: str) -> dict:
    """Parse RGB status notification."""
    if len(hex_str) < 36:
        return {"raw": hex_str, "error": "too short"}

    # feef0c11abbb0cd0 02 01 64 01 04 ff009f 02
    # Bytes:            16 17 18 19 20 21-26  27
    try:
        payload_len = int(hex_str[12:14], 16)
        version = int(hex_str[16:18], 16)
        on = int(hex_str[18:20], 16)
        brightness = int(hex_str[20:22], 16)
        timer_active = int(hex_str[22:24], 16)
        timer_min = int(hex_str[24:26], 16)

        return {
            "raw": hex_str,
            "payload_len": payload_len,
            "version": version,
            "on": on,
            "brightness": brightness,
            "timer_active": timer_active,
            "timer_min": timer_min,
        }
    except Exception as e:
        return {"raw": hex_str, "error": str(e)}

def test_command(cmd: str) -> dict:
    """Test a command and return the result."""
    print(f"\n=== Testing: {cmd} ===")

    # Send the command
    if not send_raw_cmd(cmd):
        return {"cmd": cmd, "error": "send failed"}

    time.sleep(2)

    # Request status
    send_raw_cmd("30 02")
    time.sleep(2)

    # Get last notification
    notifs = get_last_notifications(3)
    if not notifs:
        return {"cmd": cmd, "error": "no notifications"}

    # Parse the last RGB notification
    for n in reversed(notifs):
        if n[12:14] == "11":  # RGB packet (payload_len = 0x11 = 17)
            parsed = parse_rgb_notification(n)
            print(f"Notification: {n}")
            print(f"Parsed: {parsed}")
            return {"cmd": cmd, **parsed}

    return {"cmd": cmd, "error": "no RGB notification", "notifs": notifs}

def main():
    print("=== Beurer TL100 Timer Command Probe ===\n")

    # First check current state
    print("Getting current state...")
    notifs = get_last_notifications(3)
    for n in notifs:
        print(f"  {n}")

    # Commands to test
    commands = [
        # Single byte commands
        "38 0F", "39 0F", "3A 0F", "3B 0F", "3C 0F", "3D 0F", "3E 0F", "3F 0F",
        # With mode byte
        "38 02 0F", "39 02 0F", "3A 02 0F", "3B 02 0F",
        # Different formats for 33/36
        "33 0F", "36 0F",
        "33 02 0F 01", "36 02 0F 01",
        "33 0F 02", "36 0F 02",
    ]

    results = []

    for cmd in commands:
        result = test_command(cmd)
        results.append(result)

        # Check if timer is now active
        if result.get("timer_active") == 1:
            print(f"\n>>> FOUND IT! Command '{cmd}' activated the timer! <<<")
            print(f"Timer set to: {result.get('timer_min')} minutes")
            break

    print("\n=== Summary ===")
    for r in results:
        timer_status = f"timer={r.get('timer_active', '?')}:{r.get('timer_min', '?')}" if 'timer_active' in r else r.get('error', 'unknown')
        print(f"{r['cmd']}: {timer_status}")

if __name__ == "__main__":
    main()
