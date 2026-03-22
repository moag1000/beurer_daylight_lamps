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

## Complete Command Reference (from APK Reverse Engineering)

All 28 commands discovered from the Beurer LightUp APK v2.1 (decompiled with jadx).

### Common Commands (All Models)

| Cmd | Name | Payload | Description |
|-----|------|---------|-------------|
| 0x00 | Permission | `[]` | Query device control permission (response must be 2) |
| 0x01 | Time Sync | `[sec, min, hour, weekday, day, month, year-2000]` | Sync clock |
| 0x02 | Settings Write | `[display, date_fmt, time_fmt, feedback, fade]` | Write device settings |
| 0x03 | Alarm Sync | `[slot, enabled, min, hour, days, tone, vol, snooze_idx, sun_en, sun_time, sun_bright]` | Set/query alarm |
| 0x12 | Settings Read | `[]` | Query device settings |
| 0x30 | Status | `[mode]` | Request status (mode: 0x01=white, 0x02=rgb) |
| 0x31 | Brightness | `[mode, percent]` | Set brightness 0-100% |
| 0x32 | Color | `[r, g, b]` | Set RGB color 0-255 |
| 0x33 | Timer Value | `[mode, minutes]` | Set timer duration (1-120 min TL, 1-60 min WL90) |
| 0x34 | Effect | `[index]` | Set effect/scene 0-10 |
| 0x35 | Off | `[mode]` | Turn off |
| 0x36 | Timer Cancel | `[mode]` | Cancel/disable timer |
| 0x37 | Mode | `[mode]` | Switch white/rgb mode (on) |
| 0x38 | Timer Toggle | `[mode]` | Toggle timer on |

### WL90-Only Commands (Radio)

| Cmd | Name | Payload | Description |
|-----|------|---------|-------------|
| 0x04 | Radio Info | `[direction]` | Query radio with presets |
| 0x07 | Radio Status | `[]` | Query radio state |
| 0x08 | Radio Power | `[0/1]` | Radio on/off |
| 0x09 | Radio Preset | `[channel]` | Select preset (1-10, 1-based!) |
| 0x0A | Radio Tune | `[type, direction]` | type: 0=fine, 1=seek; dir: 0=down, 1=up |
| 0x0B | Radio Volume | `[volume]` | Set volume 0-10 |
| 0x0C | Radio Timer Toggle | `[0/1]` | Sleep timer on/off |
| 0x0D | Radio Timer Value | `[minutes]` | Sleep timer minutes (1-60) |
| 0x0E | Radio Save Freq | `[]` | Save current frequency to preset |

### WL90-Only Commands (Music/BT Speaker)

| Cmd | Name | Payload | Description |
|-----|------|---------|-------------|
| 0x0F | Music Query | `[]` | Check A2DP connection |
| 0x10 | Music Toggle | `[]` | Open BT speaker mode |
| 0x14 | Music Volume | `[volume]` | Set volume 0-10 |
| 0x15 | Music Timer Toggle | `[0/1]` | Sleep timer on/off |
| 0x16 | Music Timer Value | `[minutes]` | Sleep timer minutes (1-60) |
| 0x17 | Music Info | `[]` | Query volume, timer state |
| 0x24 | Music Close | `[]` | Close A2DP connection |

### Response Command Bytes (data[7])

| Resp | Name | Description |
|------|------|-------------|
| 0xD0 | Status | Normal status query response |
| 0xF0 | Permission | Device permission (data[8] must be 2) |
| 0xF1 | Time Ack | Time sync acknowledged |
| 0xF2 | Settings Ack | Settings write confirmed |
| 0xE2 | Settings Data | Settings read response |
| 0xF3 | Alarm Data | Alarm slot data |
| 0xF4 | Radio Info | Radio with 10 preset frequencies |
| 0xF7 | Radio Status | Radio state (on, channel, freq, volume, timer) |
| 0xF8 | Radio Power Ack | Radio on/off confirmed |
| 0xF9 | Radio Preset Ack | Preset selection confirmed |
| 0xFA | Radio Tune Ack | Tune/seek result with new frequency |
| 0xFE | Radio Save Ack | Frequency save confirmed |
| 0xFF | Music Status | A2DP status (includes BT address if connected) |
| 0xE0 | Music Toggle Ack | BT speaker toggle result |
| 0xE5 | Music Timer Ack | Music timer toggle result |
| 0xE7 | Music Info | Volume, timer state, timer minutes |
| 0xEB | Light Timer End | Light timer expired (1=off, 2=cancelled) |
| 0xEC | Moonlight Timer End | Moonlight timer expired |
| 0xED | Radio Timer End | Radio sleep timer expired (WL90 only) |
| 0xEE | Music Timer End | Music sleep timer expired (WL90 only) |

**Mode byte**: `0x01` = White mode, `0x02` = RGB mode

## Device Permission (CMD 0x00)

The APK always sends `CMD 0x00` before any other command. The device responds with `RESP 0xF0`:

| Response Value (data[8]) | Meaning |
|--------------------------|---------|
| 2 | Permission granted - full control |
| Other | Permission denied - another device may be connected |

## Time Sync (CMD 0x01)

Syncs the current date/time to the device clock. The APK sends this on every connect.

```
Payload: [SEC, MIN, HOUR, WEEKDAY, DAY, MONTH, YEAR-2000]
```

- WEEKDAY: 1=Monday, 7=Sunday (ISO 8601)
- YEAR: Offset from 2000 (e.g., 2026 = 26)

## Device Settings (CMD 0x02 / CMD 0x12)

### Read Settings (CMD 0x12)

Send `[0x12]` to query settings. Response `RESP 0xE2`:

| Byte | Field | Values |
|------|-------|--------|
| data[8] | Display setting | Device-specific |
| data[9] | Date format | Device-specific |
| data[10] | Time format | Device-specific |
| data[11] | Feedback sound | 0=enabled, 1=disabled (inverted!) |
| data[12] | Fade transitions | 0=enabled, 1=disabled (inverted!) |

### Write Settings (CMD 0x02)

```
Payload: [display, date_fmt, time_fmt, feedback, fade]
```

- feedback/fade: 0=enabled, 1=disabled (inverted from boolean!)
- Write confirmation response: `RESP 0xF2`

## Timer State in Status Notifications

Status notifications (version 1 and 2) contain timer state at bytes 11-12:

| Byte | Field | Values |
|------|-------|--------|
| data[11] | Timer enabled | 0=inactive, 1=active |
| data[12] | Timer minutes | Remaining minutes (only valid when enabled) |

## Timer End Notifications

When a timer expires, the device sends a special notification:

| Response CMD | Type | Description |
|--------------|------|-------------|
| 0xEB | Light timer | Light mode timer expired |
| 0xEC | Moonlight timer | Moonlight mode timer expired |

- data[8]: Result code (1=timer expired and light off, 2=timer cancelled)

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

## Timer State in Notifications (APK Discovery)

Status response packets (both White and RGB) include timer state:

| Offset | Field | Values |
|--------|-------|--------|
| data[11] | Timer enabled | 0x00 = off, 0x01 = active |
| data[12] | Timer minutes | Duration in minutes (1-120), 120 = default when inactive |

### Timer End Notifications (Unsolicited)

When a timer expires, the device sends a short notification:

| data[7] | Name | data[8] Values |
|---------|------|---------------|
| 0xEB | Light timer end | 1 = light turned off, 2 = timer cancelled |
| 0xEC | Moonlight timer end | 1 = light turned off, 2 = timer cancelled |

## Time Sync Command (0x01) — APK Discovery

Sync the current time from host to device:

```
Payload: [0x01, SECOND, MINUTE, HOUR, WEEKDAY, DAY, MONTH, YEAR]
```

| Byte | Description | Range |
|------|-------------|-------|
| SECOND | Current second | 0-59 |
| MINUTE | Current minute | 0-59 |
| HOUR | Current hour (24h) | 0-23 |
| WEEKDAY | Day of week | 1=Mon, 7=Sun |
| DAY | Day of month | 1-31 |
| MONTH | Month | 1-12 |
| YEAR | Year offset | year - 2000 (e.g., 26 for 2026) |

## Device Settings Commands (0x02, 0x12) — APK Discovery

### Query Settings (0x12)

```
Payload: [0x12]
Response: data[7]=0xE2, data[8..12] = settings
```

### Write Settings (0x02)

```
Payload: [0x02, DISPLAY, DATE_FORMAT, TIME_FORMAT, FEEDBACK, FADE]
Response: data[7]=0xF2 (confirmation)
```

| Byte | Field | Values |
|------|-------|--------|
| DISPLAY | Display mode | Device-specific |
| DATE_FORMAT | Date format | Device-specific |
| TIME_FORMAT | Time format | 0 or 1 (12h/24h) |
| FEEDBACK | Button beep | 0 = enabled, 1 = disabled (inverted!) |
| FADE | Smooth transitions | 0 = enabled, 1 = disabled (inverted!) |

**Note:** Feedback and Fade values are inverted in the protocol: 0 means ON, 1 means OFF.

## Device Permission Check (0x00) — APK Discovery

The first command after connecting. The device must respond with value `2` to allow control.

```
Send:     [0x00]
Response: data[7]=0xF0, data[8]=2 (permission granted)
```

If the response is not `2`, the device may be locked by another connection.

## Device Model Differences (from APK)

| Feature | WL90 | TL100 |
|---------|------|-------|
| Light (white/RGB) | Yes | Yes |
| Moonlight scenes | Yes (0-10) | Yes (0-10) |
| Light timer max | 60 min | 120 min |
| Alarm (3 slots) | Yes | Yes |
| FM Radio | Yes | No |
| BT Speaker (A2DP) | Yes | No |
| Settings menu | Yes | No |
| BLE name prefix | `WL_90` / `WL90` | `TL100` |

### Alarm Tones (12 options, index 0-11)

| Index | Name | Notes |
|-------|------|-------|
| 0 | Buzzer | Default beep |
| 1 | Radio | Uses FM radio (WL90 only) |
| 2-11 | Melody 1-10 | Pre-loaded melodies |

### Radio Tune Types

Command `0x0A` takes two parameters: `[TYPE] [DIRECTION]`
- TYPE=0: Fine tune (step by step)
- TYPE=1: Auto-seek (find next station)
- DIRECTION=0: Down, DIRECTION=1: Up

## Unknown Commands (To Reverse Engineer)

| Cmd | Suspected Feature |
|-----|-------------------|
| 0x39 | Unknown (not in APK) |
| 0x3E | Unknown (not in APK, possibly TL100-specific firmware) |
| 0x3F | Unknown (not in APK, possibly TL100-specific firmware) |

## Notification Responses

### Status Notifications (by version byte, data[8])

- `1` = White status (byte 9: on, byte 10: brightness, byte 11: timer_on, byte 12: timer_min)
- `2` = RGB status (byte 9: on, byte 10: brightness, byte 13-15: RGB, byte 16: effect, byte 11: timer_on, byte 12: timer_min)
- `255` = Off
- `0` = Shutdown

### Special Response Types (by command byte, data[7])

| Response CMD | Name | Description |
|--------------|------|-------------|
| 0xD0 | Status | Normal status response |
| 0xE2 | Settings Read | Device settings response |
| 0xEB | Light Timer End | Light timer expired |
| 0xEC | Moonlight Timer End | Moonlight timer expired |
| 0xF0 | Device Permission | Permission grant/deny |
| 0xF2 | Settings Write | Settings write confirmation |

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
