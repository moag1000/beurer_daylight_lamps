# Beurer Daylight Lamps

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/moag1000/beurer_daylight_lamps)
[![Validate HACS + Hassfest](https://github.com/moag1000/beurer_daylight_lamps/actions/workflows/validate-hacs-hassfest.yml/badge.svg)](https://github.com/moag1000/beurer_daylight_lamps/actions/workflows/validate-hacs-hassfest.yml)

Home Assistant integration for BLE-based Beurer daylight therapy lamps.

## Supported Devices

| Model | Status | Notes |
|-------|--------|-------|
| TL100 | Tested | Full support |
| TL50  | Untested | Should work |
| TL70  | Untested | Should work |
| TL80  | Untested | Should work |
| TL90  | Untested | Should work |

## Features

- **Bluetooth Auto-Discovery**: Lamps are automatically discovered when in range
- **On/Off Control**: Turn lamp on and off
- **Brightness Control**: Adjust white light brightness (0-100%)
- **RGB Color Mode**: Full RGB color support
- **Light Effects**: Rainbow, Pulse, Forest, Wave, and more
- **Multiple Lamps**: Support for multiple lamps simultaneously

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

## Light Effects

The following effects are available (matching the Beurer LightUp app):

- Off
- Random
- Rainbow
- Rainbow Slow
- Fusion
- Pulse
- Wave
- Chill
- Action
- Forest
- Summer

## Known Issues

1. **Connection after reboot**: Connection may fail a few times after Home Assistant reboots. The integration will auto-reconnect.

2. **Bluetooth LED always on**: The small Bluetooth indicator LED on the lamp stays illuminated while connected to Home Assistant.

## Not Supported

- **Timer**: Built-in timer functionality is not supported. Use Home Assistant automations instead.

## Debugging

Add to `configuration.yaml`:

```yaml
logger:
  default: warn
  logs:
    custom_components.beurer_daylight_lamps: debug
```

## Credits

This integration is based on the work of:

- [Bellamonte/beurer_daylight_lamps](https://github.com/Bellamonte/beurer_daylight_lamps)
- [jmac83/ha-beurer](https://github.com/jmac83/ha-beurer)
- [deadolus/ha-beurer](https://github.com/deadolus/ha-beurer)
- [sysofwan/ha-triones](https://github.com/sysofwan/ha-triones)

## License

This project is licensed under the MIT License.
