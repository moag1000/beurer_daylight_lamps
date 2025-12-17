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
- **Magic**: `0xAB 0xAA` (commands to lamp)
- **Payload Length**: Length of payload + 2
- **Payload**: Command bytes (see below)
- **Checksum**: XOR of (length + all payload bytes)
- **Trailer**: `0x55 0x0D 0x0A` (fixed)

### Response Packet (Lamp → Host)

```
┌──────┬──────┬──────┬────────┬──────┬──────┬─────────────┬───────────┬──────────┬──────┬──────┬──────┐
│ 0xFE │ 0xEF │ 0x0A │ Length │ 0xAB │ 0xBB │ Payload Len │ Payload   │ Checksum │ 0x55 │ 0x0D │ 0x0A │
└──────┴──────┴──────┴────────┴──────┴──────┴─────────────┴───────────┴──────────┴──────┴──────┴──────┘
  Byte 0  1      2       3       4      5        6          7..N        N+1       N+2    N+3    N+4
```

- **Header**: `0xFE 0xEF 0x0A` (fixed, same as command)
- **Length**: Total packet length
- **Magic**: `0xAB 0xBB` (responses from lamp) ← **Different from commands!**
- **Payload Length**: Length of payload + 2
- **Payload**: Response data (version byte at offset 1, then status data)
- **Checksum**: XOR of (length + all payload bytes)
- **Trailer**: `0x55 0x0D 0x0A` (fixed)

### Magic Byte Difference

| Direction | Magic Bytes | Meaning |
|-----------|-------------|---------|
| Host → Lamp | `0xAB 0xAA` | Command packet |
| Lamp → Host | `0xAB 0xBB` | Response/Notification packet |

### Packet Types by Payload Length

| Payload Len (Byte 6) | Type | Description |
|----------------------|------|-------------|
| `0x04` | ACK/Heartbeat | Short packet, no status data, ignore for state |
| `0x08` | White Status | Contains on/off and brightness |
| `0x0C` | RGB Status | Contains on/off, brightness, RGB, effect |

### Example: Short ACK Packet (ignore for state)

```
feef0c09abbb04d0ff2b550d0a
│    │ │ │  │ │ │ │ └────── Trailer (55 0D 0A)
│    │ │ │  │ │ │ └──────── Checksum (0x2B)
│    │ │ │  │ │ └────────── (not version - short packet!)
│    │ │ │  │ └──────────── Unknown (0xD0)
│    │ │ │  └────────────── Payload Len: 0x04 = ACK (ignore!)
│    │ │ └───────────────── Magic: 0xAB 0xBB (response)
│    │ └─────────────────── Unknown (0x09)
│    └───────────────────── Length (0x0C = 12)
└────────────────────────── Header (FE EF 0A)
```

### Example: White Status (Payload Len 0x08)

```
feef0c0dabbb08d00100640078c5550d0a
                  │ │ │
                  │ │ └─ Brightness: 0x64 = 100%
                  │ └─── On: 0x00 = OFF (white off, RGB may be on)
                  └───── Version: 0x01 = White mode
```

### Example: RGB Status (Payload Len 0x0C)

```
feef0c11abbb0cd0020115007821ff00006c550d
                  │ │ │     │ │ │ │ └─ Effect: 0x00 = Off
                  │ │ │     │ │ │ └─── B: 0x00
                  │ │ │     │ │ └───── G: 0xFF (255)
                  │ │ │     │ └─────── R: 0x21 (33)
                  │ │ │     └───────── ?? (0x78)
                  │ │ └─────────────── Brightness: 0x15 = 21%
                  │ └───────────────── On: 0x01 = YES
                  └─────────────────── Version: 0x02 = RGB mode
```

## Known Commands

| Cmd | Name | Payload | Description |
|-----|------|---------|-------------|
| 0x30 | Status | `[mode]` | Request status (mode: 0x01=white, 0x02=rgb) |
| 0x31 | Brightness | `[mode, percent]` | Set brightness 0-100% |
| 0x32 | Color | `[r, g, b]` | Set RGB color 0-255 |
| 0x34 | Effect | `[index]` | Set effect 0-10 |
| 0x35 | Off | `[mode]` | Turn off |
| 0x37 | Mode | `[mode]` | Switch white/rgb mode |
| 0x3E | Timer | `[minutes]` | Set auto-off timer (1-240 min, RGB mode only) |

## Timer Command (0x3E)

The timer command sets an auto-off timer. The lamp will automatically turn off after the specified number of minutes.

**Important**: Timer only works when the lamp is in RGB mode (0x37 0x02).

| Payload | Description |
|---------|-------------|
| `3E 0F` | 15 minute timer |
| `3E 1E` | 30 minute timer |
| `3E 3C` | 60 minute timer |
| `3E 78` | 120 minute timer |

### Example: Set 30-minute Timer

```yaml
# First ensure RGB mode
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "37 02"

# Then set timer
service: beurer_daylight_lamps.set_timer
data:
  device_id: "abc123..."
  minutes: 30
```

## Unknown Commands (To Reverse Engineer)

| Cmd | Suspected Feature |
|-----|-------------------|
| 0x33 | Unknown |
| 0x36 | Sunrise/Sunset? |
| 0x38 | Unknown |
| 0x39 | Unknown |
| 0x3F | Timer cancel? |

## Notification Responses

Byte 8 determines type:
- `1` = White status (byte 9: on, byte 10: brightness)
- `2` = RGB status (byte 9: on, byte 10: brightness, byte 13-15: RGB, byte 16: effect)
- `255` = Off
- `0` = Shutdown

## Reverse Engineering via Home Assistant UI

The integration includes a `send_raw_command` service for sending arbitrary BLE commands directly from the Home Assistant interface.

### Using Developer Tools → Services

1. Go to **Settings → Developer Tools → Services**
2. Search for `beurer_daylight_lamps.send_raw_command`
3. Fill in the fields:
   - **device_id**: Your lamp's device ID (find in Settings → Devices → Beurer Lamp → Device Info)
   - **command**: Hex bytes, e.g., `33 01 1E` or `33011E`
4. Click "Call Service"

### YAML Example

```yaml
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."  # Your device ID
  command: "33 01 1E"     # Timer 30 min?
```

### Viewing Responses

**Debug mode is only needed to see the lamp's response data.**
Without it, commands still work but you only see success/failure messages.

To enable detailed packet dumps:

1. Go to **Settings → System → Logs**
2. Filter for `beurer_daylight_lamps`
3. Set log level to DEBUG:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.beurer_daylight_lamps: debug
```

Responses appear as:
```
Notification from AA:BB:CC:DD:EE:FF: feef0a0fabaa...
```

### Commands to Probe

| Command | Payload Examples | Suspected Feature |
|---------|------------------|-------------------|
| `33` | `33 01 1E` (30min?), `33 01 3C` (60min?) | Timer |
| `36` | `36 01`, `36 00` | Sunrise/Sunset |
| `38` | `38 00`, `38 01` | Unknown |
| `39` | `39 00`, `39 01` | Unknown |

### Probing Strategy

1. **Start Simple**: Send `XX 00` and `XX 01` for unknown commands
2. **Check Response**: Look for version byte changes in notifications
3. **Vary Parameters**: Try different second bytes (0x00-0xFF)
4. **Document Findings**: Note any lamp behavior changes

### Example: Probing Timer Command

```yaml
# Try timer 15 min
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "33 01 0F"

# Try timer 30 min
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "33 01 1E"

# Try timer 60 min
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "33 01 3C"
```

---

## Reverse Engineering with BLE Sniffer (CLI Tool)

For more advanced testing, use the standalone Python sniffer tool:

```bash
python tools/ble_sniffer.py AA:BB:CC:DD:EE:FF

# Commands:
>>> probe          # Test all unknown commands
>>> raw 33 01 1E   # Send raw bytes (e.g., timer 30min?)
>>> status         # Get current status
```
