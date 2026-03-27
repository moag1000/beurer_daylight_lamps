# Contributing to Beurer Daylight Lamps

Thanks for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a new branch for your changes

## Development Setup

### Prerequisites

- Python 3.11+
- Home Assistant development environment (optional but recommended)

### Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install -r requirements_test.txt
```

### Running Tests

```bash
pytest tests/ -v
```

## Code Style

- Follow [Home Assistant's style guidelines](https://developers.home-assistant.io/docs/development_guidelines)
- Use type hints for all function parameters and return values
- Keep code simple and readable
- Add docstrings to classes and functions

## Pull Request Process

1. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Keep commits focused and atomic
   - Write clear commit messages

3. **Test your changes**
   - Run existing tests: `pytest tests/ -v`
   - Add new tests for new functionality
   - Test manually with a real device if possible

4. **Update documentation**
   - Update README.md if adding new features
   - Update CHANGELOG.md with your changes

5. **Submit a Pull Request**
   - Fill out the PR template
   - Reference any related issues
   - Be responsive to feedback

## Reporting Issues

- Use the issue templates provided
- Include debug logs when reporting bugs
- Include diagnostics export if possible
- Check existing issues before creating a new one

## Testing with a Real Device

If you have a Beurer daylight lamp (TL50, TL70, TL80, TL90, TL100, WL90):

1. Enable debug logging in Home Assistant:
   ```yaml
   logger:
     logs:
       custom_components.beurer_daylight_lamps: debug
   ```

2. Test the following scenarios:
   - Device discovery
   - On/Off control
   - Brightness control
   - RGB color changes
   - Effects
   - Reconnection after disconnect

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- Help others learn and grow

## Reverse Engineering New Features

There are three approaches to reverse engineering BLE commands:
1. **APK reverse engineering** — decompile the Beurer LightUp APK to read the protocol code directly
2. **Android BLE sniffing** — capture traffic from the official app
3. **In-app testing** — use HA's diagnostic sensors and raw command service

### Method 0: APK Reverse Engineering (Most Complete)

This is how all 28 commands and 19 response types were discovered. The Beurer LightUp APK v2.1
was decompiled using [jadx](https://github.com/skylot/jadx).

#### Key Classes (Protocol)
- `AppBytes.java` — all command builders (`getBytes()`, `syncTime()`, `queryWL90Light()`, etc.)
- `BlueOrder.java` — command/response byte constants
- `globalPool.java` — response parser (`publishBroadcast()`)

#### Communication Layer
- `SppManager.java` — connection management (singleton pattern)
- `ConnectThread.java` — Bluetooth Classic socket connection
- `ReadThread.java` — response reading (2048 byte buffer, 100ms interval)
- `WriteThread.java` — command sending
- `TimeOutRequestProxy.java` — 6-second command timeout with retry UI

#### Polling & Media
- `LoopReceiver.java` — 60-second periodic polling (BroadcastReceiver + Handler)
- `MusicCmd.java` — A2DP/BT speaker command constants (18 internal states)
- `MusicPlayService.java` — Android media session integration

#### Data Models
- `AlarmItem.java` — alarm slot data (incl. sunrise simulation params)
- `LightInfo.java` — light state model
- `MusicInfo.java` — music/speaker state model
- `RadioItem.java` — radio preset model
- `SettingItem.java` — device settings model

The APK and decompiled sources are stored in `../beurer_capture/`:
- `beurer LightUp_2.1_APKPure.apk` — original APK
- `decompiled/` — jadx output

**Note:** The APK v2.1 uses Classic BT SPP for data transfer, but the device is dual-mode.
Newer app versions switched to BLE GATT (confirmed by bugreport analysis). The packet format
is identical regardless of transport.

#### Systematic Analysis Checklist

When analyzing an APK for protocol discovery, ensure **all** classes are reviewed, not just the obvious ones:

1. **Command builders** — methods that construct byte arrays (e.g., `getBytes()`)
2. **Response parsers** — switch/case on response bytes (e.g., `publishBroadcast()`)
3. **Constants/enums** — all byte value definitions
4. **Timeout/retry** — how the app handles failed commands
5. **Polling/loop** — periodic data refresh mechanisms
6. **Data models** — what fields the app tracks per device
7. **Broadcast actions** — the full Intent action list reveals all expected events
8. **Native libraries** — check for `.so` files (Beurer has none, but other APKs may)
9. **Resources** — XML configs, assets, embedded data files

### Method 1: Android BLE Sniffing (Recommended for Discovery)

This method captures BLE traffic from the official Beurer "LightUp" app, which is useful for discovering commands you don't know about yet.

#### Step 1: Enable BLE Logging on Android

1. Enable **Developer Options** (Settings → About Phone → Tap Build Number 7x)
2. Enable **Bluetooth HCI snoop log** in Developer Options
3. Use the Beurer LightUp app extensively - test all features you want to reverse engineer

#### Step 2: Generate and Extract Bug Report

```bash
# Connect your phone via USB and run:
adb bugreport bugreport-$(date +%Y%m%d-%H%M%S).zip

# Or on the phone: Settings → Developer Options → Take Bug Report
```

#### Step 3: Extract BLE Data with btsnooz.py

The bug report contains BLE traffic in a compressed format. Use `btsnooz.py` to extract it:

```bash
# Download btsnooz.py from Android source
curl -O https://raw.githubusercontent.com/nickchan-scmp/btsnooz.py/main/btsnooz.py
chmod +x btsnooz.py

# Extract the btsnoop log
unzip bugreport-*.zip
./btsnooz.py bugreport-*.txt > btsnoop.log

# Open in Wireshark for analysis
wireshark btsnoop.log
```

#### Step 4: Filter in Wireshark

```
# Filter for your lamp's MAC address
bluetooth.src == "AA:BB:CC:DD:EE:FF" or bluetooth.dst == "AA:BB:CC:DD:EE:FF"

# Or filter for ATT protocol only
btatt
```

Look for patterns in the hex data - commands follow the format documented in `docs/PROTOCOL.md`.

### Method 2: In-App Testing

The integration includes diagnostic sensors and services for testing commands directly from Home Assistant.

#### Diagnostic Sensors (disabled by default)

Enable these in **Settings → Devices → Beurer Lamp → Entities** (show disabled):

| Sensor | Purpose |
|--------|---------|
| `Last raw notification` | All BLE notifications as hex (with history) |
| `Last unknown notification` | Only notifications with unknown version bytes |
| `Last notification version` | The version byte (1=white, 2=rgb, 255=off, 0=shutdown) |

### Workflow for Discovering New Features

1. **Enable diagnostic sensors** in Home Assistant
2. **Open History** for the sensors (especially "Last unknown notification")
3. **Trigger a feature** in the Beurer "Light Up" app (Timer, Sunrise, etc.)
4. **Check sensor history** for new data patterns
5. **Analyze the notification** to understand the protocol

### Using the Raw Command Service

Send arbitrary BLE commands via **Developer Tools → Services**:

```yaml
service: beurer_daylight_lamps.send_raw_command
data:
  device_id: "your_device_id"
  command: "33 01 1E"  # Example: Timer test
```

### Commands Status (after APK analysis)

All commands 0x00-0x38 have been fully mapped from the APK. See `docs/PROTOCOL.md` for the
complete reference. Only 3 commands remain unknown (not present in the APK):

| Cmd | Status | Notes |
|-----|--------|-------|
| `0x39` | Not in APK | Confirmed absent after exhaustive search of all Java source |
| `0x3A-0x3D` | Not in APK | Entire range unimplemented in APK |
| `0x3E` | Not in APK | Possibly TL100-specific firmware feature |
| `0x3F` | Not in APK | Possibly timer cancel or TL100-specific firmware feature |

### Example: Reverse Engineering the Timer

1. Enable "Last raw notification" and "Last unknown notification" sensors
2. In the Beurer app, set a 30-minute timer
3. Check the sensor history for new notification patterns
4. Look for a new version byte (not 1, 2, 255, or 0)
5. Decode the payload structure
6. Test your hypothesis with `send_raw_command`
7. Document findings in `docs/PROTOCOL.md`

### Notification Structure

```
Byte:  0-2    3      4-5     6        7      8         9+
       Header Length Magic   PayLen   ?      Version   Payload...
       FEEF0A        ABAA
```

- **Version 1**: White mode (byte 9: on/off, byte 10: brightness %)
- **Version 2**: RGB mode (byte 9: on/off, byte 10: brightness, bytes 13-15: RGB, byte 16: effect)
- **Version 255**: Device off
- **Version 0**: Shutdown
- **Other versions**: Unknown - please investigate and document!

### Submitting Protocol Discoveries

When you discover a new command or notification:

1. Update `docs/PROTOCOL.md` with the new information
2. Add constants to `const.py` (e.g., `CMD_TIMER = 0x33`)
3. Implement the feature in `beurer_daylight_lamps.py`
4. Add entities in the appropriate platform file
5. Update `CHANGELOG.md`
6. Submit a Pull Request!

## Questions?

Open a discussion or issue if you have questions about contributing.
