# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.4] - 2025-12-16

### Changed
- **Removed generic "Beurer" matcher**: Only matches specific TL model prefixes (TL50, TL70, TL80, TL90, TL100) to avoid conflicts with other Beurer devices

### Fixed
- **Discovery performance**: Removed characteristic-based fallback that was connecting to all BLE devices

## [1.6.3] - 2025-12-16

### Changed
- **Reliable BLE connections**: Now uses `bleak-retry-connector` for more stable Bluetooth connections
- **Integration name**: Renamed to "Beurer Daylight Therapy Lamps" to distinguish from original fork

### Fixed
- Removed warning about missing `bleak-retry-connector` in Home Assistant logs

## [1.6.2] - 2025-12-16

### Added
- **Exception translations**: Error messages are now translatable (Gold tier: exception-translations)
- **Entity translations**: Light entity name is now translatable
- **German translations**: Complete German translations for exceptions and issues
- **Additional tests**: Expanded test coverage for config flow and sensor

### Fixed
- Test for `unique_id` in sensor now expects normalized (lowercase) MAC address
- Test for `available` in sensor now tests connection state via `.available` property
- Test for device_info in sensor now expects normalized MAC in identifiers

## [1.6.1] - 2025-12-16

### Added
- **PARALLEL_UPDATES**: Limit concurrent updates to prevent BLE command conflicts (Silver tier requirement)
- **Documentation**: Added removal instructions to README
- **Documentation**: Added troubleshooting section to README

### Changed
- Moved `detect_model()` function to `const.py` (was causing circular import in tests)

### Fixed
- Test imports now correctly reference `detect_model` from `const.py`
- Test for `available` property now tests connection state, not power state
- Test for `unique_id` now expects normalized (lowercase) MAC address

## [1.6.0] - 2025-12-16

### Added
- **Repair Issues**: Connection problems now create repair issues in Home Assistant's Repairs section
  - "Device not found" issue with fix flow when device cannot be discovered
  - "Initialization failed" issue when device is found but fails to connect
- **MAC address normalization**: All unique IDs and device identifiers now use `format_mac()` for consistency

### Changed
- **DeviceInfo consistency**: Light and Sensor entities now share identical DeviceInfo (model, sw_version)
- **Removed unused Options Flow**: The scan_interval option was removed as it's not applicable to push-based BLE communication

### Fixed
- Availability logic now correctly reflects connection state, not power state
- Entities remain available when lamp is turned off (as long as BLE connection is active)

## [1.5.0] - 2024-12-16

### Added
- **Protocol documentation**: New `docs/PROTOCOL.md` with comprehensive BLE protocol documentation
- **BLE communication tests**: New test file `test_beurer_instance.py` with unit tests for:
  - Device initialization and validation
  - Callback management
  - RSSI updates
  - Notification parsing (white mode, RGB mode, device off)
  - Device discovery
- **Public properties**: New `is_connected`, `write_uuid`, `read_uuid` properties for better encapsulation
- **Public `set_color_mode()` method**: Replaces direct private attribute access
- **Rate limiting**: Commands are now rate-limited (minimum 100ms between commands) to prevent overwhelming the device

### Changed
- **Exception handling**: Replaced all bare `except Exception` with specific exceptions (`BleakError`, `TimeoutError`, `OSError`)
- **Protocol constants**: Magic numbers replaced with named constants (`CMD_STATUS`, `CMD_BRIGHTNESS`, `CMD_COLOR`, etc.)
- **Timing constants**: Hardcoded sleep delays replaced with documented constants (`COMMAND_DELAY`, `MODE_CHANGE_DELAY`, etc.)
- **MAC address normalization**: Consistent use of `format_mac()` for MAC address comparisons
- **Fire-and-forget tasks**: Added `_safe_create_task()` wrapper with proper error handling
- **Minimum HA version**: Added `homeassistant: "2024.1.0"` requirement to manifest.json
- **Simplified state management**: `is_on` property now derived from `_light_on`/`_color_on` flags, reducing redundant state

### Fixed
- Removed unused `CMD_MODE_WHITE` and `CMD_MODE_RGB` constants (both were 0x37, now unified as `CMD_MODE`)
- Diagnostics no longer accesses private `_client`, `_write_uuid`, `_read_uuid` attributes

## [1.4.0] - 2024-12-16

### Added
- **Diagnostics support**: Export debug information via Settings → Devices & Services
- **RSSI sensor**: Optional signal strength sensor (disabled by default)
- **Reconfigure flow**: Change device name after initial setup
- **RSSI update on reconnect**: Signal strength is refreshed when reconnecting to device

### Changed
- Callback system now supports multiple listeners (fixes issue with sensor not updating)
- `get_device()` now returns tuple `(device, rssi)` for better RSSI tracking

### Fixed
- Light and sensor entities now both receive state updates correctly

## [1.3.0] - 2024-12-16

### Added
- Unit tests for config flow, light entity, and integration setup
- Reauth flow for handling connection loss
- Options flow for configuring scan interval
- GitHub Actions workflow for running tests

## [1.2.0] - 2024-12-16

### Changed
- Refactored code to follow Home Assistant best practices
- Moved constants to dedicated `const.py` file
- Improved type hints throughout codebase
- Changed `integration_type` from "hub" to "device"
- Changed `iot_class` from "local_polling" to "local_push"

### Fixed
- Removed unused imports
- Consistent use of `ColorMode` enum

## [1.1.0] - 2024-12-16

### Added
- Bluetooth auto-discovery for TL50, TL70, TL80, TL90, TL100 models
- `async_step_bluetooth()` and `async_step_bluetooth_confirm()` in config flow
- Bluetooth matchers in manifest.json

### Changed
- Added `bluetooth_adapters` dependency

## [1.0.0] - Initial Fork

### Added
- Forked from [Bellamonte/beurer_daylight_lamps](https://github.com/Bellamonte/beurer_daylight_lamps)
- Full support for TL100 daylight therapy lamp
- On/Off control, brightness control, RGB color mode
- Light effects (Rainbow, Pulse, Forest, Wave, etc.)
- HACS compatibility
