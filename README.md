# Beurer Daylight Therapy Lamps

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/moag1000/beurer_daylight_lamps)](https://github.com/moag1000/beurer_daylight_lamps/releases)
[![Validate](https://github.com/moag1000/beurer_daylight_lamps/actions/workflows/validate-hacs-hassfest.yml/badge.svg)](https://github.com/moag1000/beurer_daylight_lamps/actions/workflows/validate-hacs-hassfest.yml)
[![Tests](https://github.com/moag1000/beurer_daylight_lamps/actions/workflows/tests.yml/badge.svg)](https://github.com/moag1000/beurer_daylight_lamps/actions/workflows/tests.yml)

Home Assistant custom integration for Beurer daylight therapy lamps via Bluetooth Low Energy (BLE).

## Supported Devices

| Model | Status | Notes |
|-------|--------|-------|
| TL100 | ✅ Tested | Full support |
| TL50  | ⚠️ Untested | Should work |
| TL70  | ⚠️ Untested | Should work |
| TL80  | ⚠️ Untested | Should work |
| TL90  | ⚠️ Untested | Should work |

## Features

### Light Control
- 💡 On/off and brightness control
- 🎨 RGB color mode with color picker
- 🌡️ Color temperature (2700K - 6500K)
- ✨ Light effects (Rainbow, Pulse, Forest, Wave, etc.)
- 🔆 Separate white/color brightness sliders

### Connectivity
- 📡 Bluetooth auto-discovery
- 🔄 ESPHome/Shelly Bluetooth Proxy support
- 📶 Automatic adapter switching to best signal
- 🔗 Connection status monitoring

### Entities Created

| Entity Type | Name | Description |
|-------------|------|-------------|
| **Light** | Beurer Lamp | Main light entity with all controls |
| **Button** | Identify | Blinks lamp 3x to find it |
| **Button** | Reconnect | Forces BLE reconnection |
| **Select** | Effect | Dropdown for light effects |
| **Number** | White brightness | Slider 0-100% |
| **Number** | Color brightness | Slider 0-100% |
| **Sensor** | Signal strength | RSSI in dBm (disabled by default) |
| **Binary Sensor** | Connected | BLE connection status |
| **Binary Sensor** | Bluetooth reachable | Device seen by any adapter |

### Services

#### `beurer_daylight_lamps.apply_preset`

Apply predefined lighting presets:

| Preset | Description |
|--------|-------------|
| `daylight_therapy` | Full brightness 5300K for therapy |
| `relax` | Warm dim light (2700K, 40%) |
| `focus` | Cool bright light (5000K, 90%) |
| `reading` | Neutral white (4000K, 80%) |
| `warm_cozy` | Very warm (2700K, 60%) |
| `cool_bright` | Cool white full brightness |
| `sunset` | Orange sunset simulation |
| `night_light` | Very dim warm light |
| `energize` | Bright cool light to wake up |

Example usage:
```yaml
service: beurer_daylight_lamps.apply_preset
data:
  device_id: "abc123..."
  preset: daylight_therapy
```

#### `beurer_daylight_lamps.set_timer`

Set an auto-off timer (1-240 minutes). The lamp will turn off automatically after the specified time.

```yaml
service: beurer_daylight_lamps.set_timer
data:
  device_id: "abc123..."
  minutes: 30
```

**Note**: Timer only works in RGB/color mode. Use it with color or effect settings.

## Installation

> **Note:** Restart Home Assistant after installation.

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add `https://github.com/moag1000/beurer_daylight_lamps` as "Integration"
5. Search for "Beurer Daylight Lamps" and install

### Manual Installation

```bash
git clone https://github.com/moag1000/beurer_daylight_lamps
cd beurer_daylight_lamps
cp -r custom_components/beurer_daylight_lamps ~/.homeassistant/custom_components/
```

## Removal

1. Go to **Settings** → **Devices & Services**
2. Find the Beurer Daylight Lamps integration
3. Click the three dots menu → **Delete**
4. Restart Home Assistant
5. (Optional) Remove the integration folder from `custom_components/`

## Setup

### Automatic Discovery (recommended)

1. Turn on your Beurer lamp
2. Home Assistant will automatically detect the lamp via Bluetooth
3. A notification will appear - click "Configure"
4. The lamp will blink to confirm connection
5. Click "Submit" to complete setup

### Manual Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Beurer Daylight Lamps"
3. Select your lamp from the list or enter MAC address manually
4. The lamp will blink to confirm - click "Yes" if it blinked

## Bluetooth Proxy Support

This integration fully supports ESPHome and Shelly Bluetooth Proxies:

- Automatically uses the proxy with the best signal
- Seamlessly switches between adapters as signal changes
- No configuration needed - just set up your proxies in Home Assistant

## Light Effects

The following effects are available (matching the Beurer LightUp app):

| Effect | Description |
|--------|-------------|
| Off | No effect |
| Random | Random color changes |
| Rainbow | Smooth rainbow cycle |
| Rainbow Slow | Slower rainbow cycle |
| Fusion | Color fusion effect |
| Pulse | Pulsing brightness |
| Wave | Wave-like transitions |
| Chill | Relaxing color changes |
| Action | Dynamic color changes |
| Forest | Green/nature tones |
| Summer | Warm summer colors |

## Example Automations

### Wake-up Light with Preset

```yaml
automation:
  - alias: "Wake-up light"
    trigger:
      - platform: time
        at: "06:30:00"
    condition:
      - condition: workday
        country: DE
    action:
      - service: beurer_daylight_lamps.apply_preset
        data:
          device_id: !input beurer_device
          preset: energize
```

### Gradual Wake-up

```yaml
automation:
  - alias: "Gradual wake-up light"
    trigger:
      - platform: time
        at: "06:30:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.beurer_tl100
        data:
          color_temp_kelvin: 2700
          brightness: 25
      - delay: "00:05:00"
      - service: light.turn_on
        target:
          entity_id: light.beurer_tl100
        data:
          color_temp_kelvin: 4000
          brightness: 128
      - delay: "00:05:00"
      - service: light.turn_on
        target:
          entity_id: light.beurer_tl100
        data:
          color_temp_kelvin: 5300
          brightness: 255
```

### Evening Mood Light

```yaml
automation:
  - alias: "Evening mood light"
    trigger:
      - platform: sun
        event: sunset
    action:
      - service: beurer_daylight_lamps.apply_preset
        data:
          device_id: !input beurer_device
          preset: sunset
```

### Light Therapy Session

```yaml
automation:
  - alias: "Morning light therapy"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: beurer_daylight_lamps.apply_preset
        data:
          device_id: !input beurer_device
          preset: daylight_therapy
      - delay: "00:30:00"
      - service: light.turn_off
        target:
          entity_id: light.beurer_tl100
```

## Known Issues

1. **Connection after reboot**: Connection may fail a few times after Home Assistant reboots. The integration will auto-reconnect.

2. **Bluetooth LED always on**: The small Bluetooth indicator LED on the lamp stays illuminated while connected to Home Assistant.

## Not Supported

- **Sunrise/Sunset simulation**: Hardware feature not yet implemented. Use automations with gradual brightness changes.

## Diagnostics

To download diagnostic information for troubleshooting:

1. Go to **Settings** → **Devices & Services**
2. Click on the Beurer Daylight Lamps integration
3. Click the three dots menu → **Download diagnostics**

The diagnostic file contains device state, connection info, and configuration (MAC address is redacted).

## Signal Strength Sensor

An optional RSSI (Received Signal Strength Indicator) sensor is available for each lamp. This sensor is disabled by default.

To enable:
1. Go to **Settings** → **Devices & Services** → **Beurer Daylight Lamps**
2. Click on your device
3. Find "Signal strength" under disabled entities
4. Click and enable it

The RSSI value (in dBm) indicates Bluetooth signal quality:
- `-30 to -50 dBm`: Excellent
- `-50 to -70 dBm`: Good
- `-70 to -85 dBm`: Fair
- `< -85 dBm`: Poor (may cause connection issues)

## Troubleshooting

### Lamp not discovered

1. Ensure the lamp is powered on and not connected to another device (e.g., Beurer LightUp app)
2. Check that your Home Assistant host has Bluetooth enabled
3. Move the lamp closer to your Home Assistant host (within 10 meters)
4. Try restarting the lamp by unplugging and plugging it back in
5. Check **Settings** → **System** → **Repairs** for any connection issues

### Connection keeps dropping

1. Check the signal strength sensor (enable it under the device's disabled entities)
2. If RSSI is below -80 dBm, move the lamp closer or use a Bluetooth adapter with better range
3. Ensure no other devices are interfering with Bluetooth (e.g., USB 3.0 devices near the adapter)
4. **Recommended**: Use an ESPHome Bluetooth Proxy for better range and reliability

### Lamp responds slowly

1. The integration limits commands to prevent overwhelming the BLE device
2. Multiple rapid commands may be queued (100ms minimum between commands)
3. This is normal behavior to ensure reliable communication

### Entity shows unavailable

1. The lamp may have lost Bluetooth connection
2. Check **Settings** → **System** → **Repairs** for repair issues
3. Try using the "Reconnect" button entity
4. Try turning the lamp off and on again
5. The integration will automatically try to reconnect

## Debugging

Add to `configuration.yaml`:

```yaml
logger:
  default: warn
  logs:
    custom_components.beurer_daylight_lamps: debug
```

## BLE Protocol Reverse Engineering

A sniffer tool is included for reverse engineering additional features:

```bash
pip install bleak
python tools/ble_sniffer.py AA:BB:CC:DD:EE:FF
```

Commands:
- `status` - Request current status
- `probe` - Test unknown commands (0x33, 0x36, 0x38, 0x39)
- `raw 33 01 0A` - Send raw bytes

Contributions for Timer and Sunrise/Sunset features welcome!

## Credits

Based on work by:
- [sysofwan/ha-triones](https://github.com/sysofwan/ha-triones)
- [deadolus/ha-beurer](https://github.com/deadolus/ha-beurer)
- [jmac83/ha-beurer](https://github.com/jmac83/ha-beurer)
- [Bellamonte/beurer_daylight_lamps](https://github.com/Bellamonte/beurer_daylight_lamps)

## License

This project is licensed under the MIT License.
