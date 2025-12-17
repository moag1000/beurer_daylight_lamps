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

### Lifestyle Wellness Features

> **Important**: These features are for personal lifestyle tracking and wellness purposes only. This integration is **NOT a medical device** and should not be used for medical purposes.

- **Sunrise/Sunset Simulation**: Native integration layer simulation with gradual brightness and color temperature changes
- **Light Exposure Tracking**: Track daily and weekly bright light exposure minutes
- **Daily Goal Progress**: Configurable daily light exposure goal with progress sensor
- **Goal Reached Notification**: Binary sensor for automation triggers when daily goal is met

### Entities Created

| Entity Type | Name | Description |
|-------------|------|-------------|
| **Light** | Beurer Lamp | Main light entity with all controls |
| **Button** | Identify | Blinks lamp 3x to find it |
| **Button** | Reconnect | Forces BLE reconnection |
| **Select** | Effect | Dropdown for light effects |
| **Number** | White brightness | Slider 0-100% |
| **Number** | Color brightness | Slider 0-100% |
| **Number** | Timer | Auto-off timer 1-240 min (RGB mode only) |
| **Number** | Daily light goal | Configurable daily exposure goal (5-120 min) |
| **Sensor** | Signal strength | RSSI in dBm (disabled by default) |
| **Sensor** | Light exposure today | Minutes of bright light today |
| **Sensor** | Light exposure this week | Minutes of bright light this week |
| **Sensor** | Daily goal progress | Percentage of daily goal completed |
| **Binary Sensor** | Connected | BLE connection status |
| **Binary Sensor** | Bluetooth reachable | Device seen by any adapter |
| **Binary Sensor** | Daily goal reached | True when daily exposure goal is met |

#### Entity Notes

- **Timer**: Only available in RGB mode (see [Known Limitations](#known-limitations))
- **Signal Strength**: Disabled by default. RSSI values: -30 to -50 dBm = excellent, -50 to -70 = good, < -80 = poor

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

#### `beurer_daylight_lamps.start_sunrise`

Start a sunrise simulation with gradual brightness and color temperature increase.

> **Lifestyle Feature**: This is a personal wellness feature, not a medical device.

```yaml
service: beurer_daylight_lamps.start_sunrise
data:
  device_id: "abc123..."
  duration: 15  # minutes (1-60)
  profile: natural  # gentle, natural, energize, or therapy
```

**Profiles:**
| Profile | Description |
|---------|-------------|
| `gentle` | Slow, soft transition for sensitive users |
| `natural` | Mimics natural sunrise timing |
| `energize` | Faster transition with brighter end point |
| `therapy` | Optimized for bright light exposure |

#### `beurer_daylight_lamps.start_sunset`

Start a sunset simulation with gradual brightness decrease and warm color shift.

```yaml
service: beurer_daylight_lamps.start_sunset
data:
  device_id: "abc123..."
  duration: 30  # minutes (1-60)
  end_brightness: 0  # 0-100%, 0 = turn off at end
```

#### `beurer_daylight_lamps.stop_simulation`

Stop any running sunrise or sunset simulation.

```yaml
service: beurer_daylight_lamps.stop_simulation
data:
  device_id: "abc123..."
```

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

## Blueprints

Three ready-to-use blueprints are included for common lighting scenarios:

| Blueprint | Use Case |
|-----------|----------|
| **Morning Light Therapy** | Wake-up with sunrise simulation + therapy session |
| **Evening Wind Down** | Gradual dimming at sunset for better sleep |
| **Focus Work Session** | Alerting light for productivity with break reminders |

### Installation

1. Copy the `blueprints/automation/` folder contents to your Home Assistant's `config/blueprints/automation/beurer_daylight_lamps/` folder
2. Restart Home Assistant or reload automations
3. Go to **Settings** → **Automations & Scenes** → **Blueprints**
4. Find the Beurer blueprints and click "Create Automation"

### Morning Light Therapy

Simulates a natural sunrise followed by full light therapy.

- Gradual warm-to-cool transition (2700K → 5300K)
- Configurable sunrise duration (0-30 min)
- Therapy session at full brightness (10-60 min)
- Schedule: Workdays, weekends, or every day
- End behavior: Off, stay on, or switch to reading light

### Evening Wind Down

Prepares you for sleep by gradually dimming to warm light.

- Triggers at sunset or fixed time
- Gradual dimming over 15-120 minutes
- Warm light only (2700K) to avoid blue light
- Configurable start and end brightness

### Focus Work Session

Optimizes your environment for concentration.

- Cool, alerting light (4000K-6500K configurable)
- Optional Pomodoro-style break reminders
- Work sessions from 15-120 minutes
- End with relaxing light or turn off

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

## Data Updates & Communication

### How Data is Updated

This integration uses **Bluetooth Low Energy (BLE)** for communication:

- **State Updates**: The lamp sends BLE notifications when its state changes. These are processed in real-time.
- **RSSI Updates**: Signal strength is updated whenever the lamp sends a Bluetooth advertisement (typically every few seconds).
- **Polling**: No polling is required - all updates are push-based via BLE notifications.
- **Command Timing**: Commands are rate-limited to 100ms minimum between sends to prevent overwhelming the device.
- **Mode Changes**: Mode switches (white <-> RGB) include a 500ms delay to allow the hardware to stabilize.

### Latency Expectations

| Operation | Typical Latency |
|-----------|-----------------|
| On/Off | 100-300ms |
| Brightness change | 100-200ms |
| Color change | 150-300ms |
| Effect change | 200-500ms |
| Status update | Real-time (push) |

## Known Limitations

> **Note**: These are design constraints, not bugs.

1. **Timer only in RGB mode**: The auto-off timer (0x3E command) only functions when the lamp is in RGB/color mode. This is a hardware limitation of the Beurer protocol.

2. **Bluetooth LED always on**: The small Bluetooth indicator LED on the lamp stays illuminated while connected to Home Assistant. This cannot be disabled.

3. **Single connection**: The lamp can only maintain one BLE connection at a time. You cannot use the Beurer LightUp app while connected to Home Assistant.

4. **Connection after reboot**: Connection may fail a few times after Home Assistant reboots while the Bluetooth stack initializes. The integration will auto-reconnect.

5. **Light exposure tracking resets daily**: The therapy/exposure tracking resets at midnight. Historical data beyond the current week is not retained.

6. **Simulation requires connection**: Sunrise/sunset simulations require an active BLE connection. If the connection drops, the simulation will pause and resume when reconnected.

7. **Color temperature approximation**: Color temperatures are approximated using RGB values since the lamp doesn't have a native CT mode. Results may vary slightly from true Kelvin values.

## Diagnostics

To download diagnostic information for troubleshooting:

1. Go to **Settings** → **Devices & Services**
2. Click on the Beurer Daylight Lamps integration
3. Click the three dots menu → **Download diagnostics**

The diagnostic file contains device state, connection info, and configuration (MAC address is redacted).

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

### Effects not showing correctly

1. Some effects only work at specific brightness levels
2. Try setting brightness to 100% first, then apply the effect
3. The "Off" effect disables all effects and returns to static color

## Debugging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: warn
  logs:
    custom_components.beurer_daylight_lamps: debug
```

For detailed debugging and reverse engineering information, see [CONTRIBUTING.md](CONTRIBUTING.md).

## BLE Protocol

For developers interested in the BLE protocol or contributing new features, see:
- [docs/PROTOCOL.md](docs/PROTOCOL.md) - BLE protocol documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development and reverse engineering guide

## Credits

Based on work by:
- [sysofwan/ha-triones](https://github.com/sysofwan/ha-triones)
- [deadolus/ha-beurer](https://github.com/deadolus/ha-beurer)
- [jmac83/ha-beurer](https://github.com/jmac83/ha-beurer)
- [Bellamonte/beurer_daylight_lamps](https://github.com/Bellamonte/beurer_daylight_lamps)

## License

This project is licensed under the MIT License.
