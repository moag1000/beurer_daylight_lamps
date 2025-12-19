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
| 0x33 | Timer Value | `[mode, minutes]` | Set timer duration (1-120 min) |
| 0x34 | Effect | `[index]` | Set effect 0-10 |
| 0x35 | Off | `[mode]` | Turn off |
| 0x36 | Timer Cancel | `[mode]` | Cancel/disable timer |
| 0x37 | Mode | `[mode]` | Switch white/rgb mode |
| 0x38 | Timer Toggle | `[mode]` | Toggle timer on (at current/default duration) |

**Mode byte**: `0x01` = White mode, `0x02` = RGB mode

## Timer Commands (0x33, 0x36, 0x38)

The timer functionality uses three commands:

| Command | Payload | Description |
|---------|---------|-------------|
| `0x38 MODE` | 2 bytes | Toggle timer ON (uses current or default 120 min) |
| `0x33 MODE MINUTES` | 3 bytes | Set timer duration in minutes (1-120) |
| `0x36 MODE` | 2 bytes | Cancel/disable timer |

**Important Notes:**
- Timer works in BOTH White and RGB mode
- The MODE byte must match the current lamp mode
- Timer is automatically cancelled when switching modes (White ↔ RGB)
- Physical display shows nearest preset (45/90/120), but internal countdown uses exact value

### Example: Set 30-minute Timer (White Mode)

```yaml
# Step 1: Toggle timer on
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "38 01"

# Step 2: Set duration to 30 minutes
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "33 01 1E"
```

### Example: Set 60-minute Timer (RGB Mode)

```yaml
# Step 1: Toggle timer on
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "38 02"

# Step 2: Set duration to 60 minutes
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "33 02 3C"
```

### Using the set_timer Service

The integration provides a convenient service that handles both commands:

```yaml
service: beurer_daylight_lamps.set_timer
data:
  device_id: "abc123..."
  minutes: 45
```

### Cancel Timer

```yaml
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "36 01"  # White mode, use "36 02" for RGB mode
```

## Unknown Commands (To Reverse Engineer)

| Cmd | Suspected Feature |
|-----|-------------------|
| 0x39 | Unknown |
| 0x3E | Unknown (previously thought to be timer) |
| 0x3F | Unknown |

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
   - **command**: Hex bytes, e.g., `36 01` or `3601`
4. Click "Call Service"

### YAML Example

```yaml
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."  # Your device ID
  command: "36 01"        # Test unknown command
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
| `39` | `39 00`, `39 01` | Unknown |
| `3E` | `3E 00`, `3E 01` | Unknown |
| `3F` | `3F 00`, `3F 01` | Unknown |

**Confirmed Commands:**
- Timer toggle: `0x38 MODE`
- Timer value: `0x33 MODE MINUTES`
- Timer cancel: `0x36 MODE`

### Probing Strategy

1. **Start Simple**: Send `XX 00` and `XX 01` for unknown commands
2. **Check Response**: Look for version byte changes in notifications
3. **Vary Parameters**: Try different second bytes (0x00-0xFF)
4. **Document Findings**: Note any lamp behavior changes

### Example: Testing Unknown Commands

```yaml
# Test unknown command 0x39
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "39 01"
```

```yaml
# Test unknown command 0x3E
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "abc123..."
  command: "3E 01"
```

**For timer functionality, use the dedicated service:**

```yaml
# Set 45-minute timer (works in both White and RGB mode)
service: beurer_daylight_lamps.set_timer
data:
  device_id: "abc123..."
  minutes: 45
```

---

## Reverse Engineering with BLE Sniffer (CLI Tool)

For more advanced testing, use the standalone Python sniffer tool:

```bash
python tools/ble_sniffer.py AA:BB:CC:DD:EE:FF

# Commands:
>>> probe          # Test all unknown commands
>>> raw 3E 1E      # Send raw bytes (e.g., timer 30min)
>>> raw 36 01      # Test unknown command 0x36
>>> status         # Get current status
```
