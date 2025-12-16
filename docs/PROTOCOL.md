# Beurer TL100 BLE Protocol Documentation

This document describes the Bluetooth Low Energy (BLE) protocol used by Beurer TL daylight therapy lamps.

## BLE Characteristics

| UUID | Direction | Description |
|------|-----------|-------------|
| `8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3` | Write | Send commands to lamp |
| `0734594a-a8e7-4b1a-a6b1-cd5243059a57` | Notify | Receive status updates |

## Packet Structure

### Command Packet (Host → Lamp)

```
┌──────┬──────┬──────┬────────┬──────┬──────┬─────────────┬───────────┬──────────┬──────┬──────┬──────┐
│ 0xFE │ 0xEF │ 0x0A │ Length │ 0xAB │ 0xAA │ Payload Len │ Payload   │ Checksum │ 0x55 │ 0x0D │ 0x0A │
└──────┴──────┴──────┴────────┴──────┴──────┴─────────────┴───────────┴──────────┴──────┴──────┴──────┘
  Byte 0  1      2       3       4      5        6          7..N        N+1       N+2    N+3    N+4
```

- **Header**: `0xFE 0xEF 0x0A` (fixed)
- **Length**: Total packet length (payload_len + 7)
- **Magic**: `0xAB 0xAA` (fixed)
- **Payload Length**: Length of payload + 2
- **Payload**: Command bytes (see below)
- **Checksum**: XOR of (length + all payload bytes)
- **Trailer**: `0x55 0x0D 0x0A` (fixed)

## Known Commands

| Cmd | Name | Payload | Description |
|-----|------|---------|-------------|
| 0x30 | Status | `[mode]` | Request status (mode: 0x01=white, 0x02=rgb) |
| 0x31 | Brightness | `[mode, percent]` | Set brightness 0-100% |
| 0x32 | Color | `[r, g, b]` | Set RGB color 0-255 |
| 0x34 | Effect | `[index]` | Set effect 0-10 |
| 0x35 | Off | `[mode]` | Turn off |
| 0x37 | Mode | `[mode]` | Switch white/rgb mode |

## Unknown Commands (To Reverse Engineer)

| Cmd | Suspected Feature |
|-----|-------------------|
| 0x33 | Timer? |
| 0x36 | Sunrise/Sunset? |
| 0x38 | Unknown |
| 0x39 | Unknown |

## Notification Responses

Byte 8 determines type:
- `1` = White status (byte 9: on, byte 10: brightness)
- `2` = RGB status (byte 9: on, byte 10: brightness, byte 13-15: RGB, byte 16: effect)
- `255` = Off
- `0` = Shutdown

## Reverse Engineering with BLE Sniffer

```bash
python tools/ble_sniffer.py AA:BB:CC:DD:EE:FF

# Commands:
>>> probe          # Test all unknown commands
>>> raw 33 01 1E   # Send raw bytes (e.g., timer 30min?)
>>> status         # Get current status
```
