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

If you have a Beurer daylight lamp (TL50, TL70, TL80, TL90, TL100):

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

The integration includes diagnostic sensors and services to help discover undocumented BLE commands.

### Diagnostic Sensors (disabled by default)

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

### Commands to Investigate

| Cmd | Suspected Feature | Test Payloads |
|-----|-------------------|---------------|
| `0x33` | Timer | `33 01 0F` (15min?), `33 01 1E` (30min?) |
| `0x36` | Sunrise/Sunset | `36 01`, `36 00` |
| `0x38` | Unknown | `38 00`, `38 01` |
| `0x39` | Unknown | `39 00`, `39 01` |

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
