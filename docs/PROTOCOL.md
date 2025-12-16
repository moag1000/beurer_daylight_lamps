# Beurer Daylight Lamp BLE Protocol Documentation

This document describes the Bluetooth Low Energy (BLE) protocol used to communicate with Beurer TL50/TL70/TL80/TL90/TL100 daylight therapy lamps.

## Overview

The lamps use a custom BLE GATT service with two characteristics:
- **Write Characteristic**: `8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3` - Used to send commands
- **Read Characteristic**: `0734594a-a8e7-4b1a-a6b1-cd5243059a57` - Used to receive notifications

## Packet Structure

All commands follow this packet structure:

```
[Header] [Length] [Payload Header] [Payload Length] [Command] [Data...] [Checksum] [Trailer]
```

### Byte Layout

| Offset | Bytes | Value | Description |
|--------|-------|-------|-------------|
| 0-1 | 2 | `0xFE 0xEF` | Packet header |
| 2 | 1 | `0x0A` | Unknown (always 0x0A) |
| 3 | 1 | `len + 7` | Total packet length |
| 4-5 | 2 | `0xAB 0xAA` | Payload header |
| 6 | 1 | `len + 2` | Payload length |
| 7+ | n | varies | Command + Data |
| -4 | 1 | varies | Checksum (XOR of payload length and all command/data bytes) |
| -3 to -1 | 3 | `0x55 0x0D 0x0A` | Packet trailer |

### Example Packet

Turn on white mode at 50% brightness:
```
FE EF 0A 0C AB AA 05 31 01 32 06 55 0D 0A
│  │  │  │  │  │  │  │  │  │  │  └─────── Trailer
│  │  │  │  │  │  │  │  │  │  └────────── Checksum: 5 ^ 0x31 ^ 0x01 ^ 0x32 = 0x06
│  │  │  │  │  │  │  │  │  └───────────── Brightness: 50 (0x32)
│  │  │  │  │  │  │  │  └──────────────── Mode: White (0x01)
│  │  │  │  │  │  │  └─────────────────── Command: Brightness (0x31)
│  │  │  │  │  │  └────────────────────── Payload length: 5
│  │  │  │  │  └───────────────────────── Payload header
│  │  │  │  └──────────────────────────── Payload header
│  │  │  └─────────────────────────────── Total length: 12
│  │  └────────────────────────────────── Unknown byte
│  └───────────────────────────────────── Header
└──────────────────────────────────────── Header
```

## Commands

### 0x30 - Request Status

Request current device status. Response is sent via notification.

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x30` | Command |
| 1 | `0x01` or `0x02` | Mode: 0x01=white, 0x02=RGB |

### 0x31 - Set Brightness

Set brightness level (0-100%).

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x31` | Command |
| 1 | `0x01` or `0x02` | Mode: 0x01=white, 0x02=RGB |
| 2 | `0x00-0x64` | Brightness percentage (0-100) |

### 0x32 - Set RGB Color

Set RGB color values.

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x32` | Command |
| 1 | `0x00-0xFF` | Red value (0-255) |
| 2 | `0x00-0xFF` | Green value (0-255) |
| 3 | `0x00-0xFF` | Blue value (0-255) |

### 0x34 - Set Effect

Set light effect.

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x34` | Command |
| 1 | `0x00-0x0A` | Effect index (see table below) |

**Effect Index Table:**

| Index | Effect Name |
|-------|-------------|
| 0 | Off (solid color) |
| 1 | Random |
| 2 | Rainbow |
| 3 | Rainbow Slow |
| 4 | Fusion |
| 5 | Pulse |
| 6 | Wave |
| 7 | Chill |
| 8 | Action |
| 9 | Forest |
| 10 | Summer |

### 0x35 - Turn Off

Turn off the lamp.

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x35` | Command |
| 1 | `0x01` or `0x02` | Mode: 0x01=white, 0x02=RGB |

**Note:** To fully turn off, send for both modes.

### 0x37 - Set Mode

Switch between white and RGB mode.

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x37` | Command |
| 1 | `0x01` or `0x02` | Mode: 0x01=white, 0x02=RGB |

## Notifications (Status Responses)

The device sends notifications on the read characteristic with status information.

### Notification Structure

| Offset | Description |
|--------|-------------|
| 0-7 | Header/padding |
| 8 | Version/mode indicator |
| 9+ | Mode-specific data |

### Version Byte (offset 8)

| Value | Meaning |
|-------|---------|
| 1 | White mode status |
| 2 | RGB mode status |
| 255 | Device off |
| 0 | Device shutdown |

### White Mode Status (version=1)

| Offset | Description |
|--------|-------------|
| 8 | Version: 1 |
| 9 | On state: 0=off, 1=on |
| 10 | Brightness percentage (0-100) |

### RGB Mode Status (version=2)

| Offset | Description |
|--------|-------------|
| 8 | Version: 2 |
| 9 | On state: 0=off, 1=on |
| 10 | Brightness percentage (0-100) |
| 11-12 | Unknown |
| 13 | Red value (0-255) |
| 14 | Green value (0-255) |
| 15 | Blue value (0-255) |
| 16 | Effect index (0-10) |

## Timing Considerations

The device requires delays between commands to process them correctly:

| Operation | Recommended Delay |
|-----------|-------------------|
| Standard command | 300ms |
| Mode change | 500ms |
| Effect change | 500ms |
| Status request | 200ms |
| After turn off | 150ms |

## Device Discovery

Beurer lamps advertise with these local name prefixes:
- `TL100*`
- `TL50*`
- `TL70*`
- `TL80*`
- `TL90*`
- `Beurer*`

All devices should be connectable and support the characteristic UUIDs listed above.

## Checksum Calculation

The checksum is calculated by XORing the payload length with all command/data bytes:

```python
def calculate_checksum(payload_length: int, data: list[int]) -> int:
    result = payload_length
    for byte in data:
        result ^= byte
    return result
```

## References

- Original reverse engineering: [Bellamonte/beurer_daylight_lamps](https://github.com/Bellamonte/beurer_daylight_lamps)
- This fork: [moag1000/beurer_daylight_lamps](https://github.com/moag1000/beurer_daylight_lamps)
