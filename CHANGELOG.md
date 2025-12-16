# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.7] - 2025-12-16

### Fixed
- **ESPHome Bluetooth Proxy Support**: Verbindung über Proxies sollte jetzt funktionieren
  - `ble_device_callback` hinzugefügt - holt bei jedem Retry frisches Device von HA
  - `BleakClientWithServiceCache` für schnellere Reconnects
  - 5 Retry-Versuche statt 3 für Proxy-Verbindungen
- **Dynamische Device-Referenz**: Bei jedem Verbindungsversuch wird das beste verfügbare Device geholt

## [1.8.6] - 2025-12-16

### Fixed
- **Kritischer Bug: BleakClient wurde nie aktualisiert**: Der BLE Client wurde bei der Initialisierung erstellt und nie aktualisiert wenn ein besserer Proxy gefunden wurde
  - Client wird jetzt erst bei `connect()` erstellt mit dem aktuellen Device
  - Ermöglicht dynamisches Wechseln zwischen Bluetooth-Adaptern/Proxies
- **Null-Pointer Checks**: Alle `_client.is_connected` Aufrufe prüfen jetzt zuerst ob `_client` existiert

## [1.8.5] - 2025-12-16

### Fixed
- **Config Flow hängt nicht mehr**: 45-Sekunden Timeout für Verbindungstest hinzugefügt
- **Non-connectable Geräte**: Klare Warnung wenn Gerät nicht verbindbar ist
  - Geräteliste zeigt "(via Proxy)" für solche Geräte
  - Logs zeigen klare Fehlermeldung mit Hinweis (Sleep-Modus, Entfernung)
- **Verbesserte Verbindungslogik**: Bevorzugt jetzt explizit connectable Geräte

## [1.8.2] - 2025-12-16

### Fixed
- **Color Temperature RGB conversion bug**: Fixed `TypeError: unsupported operand type(s) for ^=: 'int' and 'float'` when setting color temperature
  - `color_temperature_to_rgb()` returns floats, now properly converted to integers
- **Device discovery resilience**: Integration now starts even when device is not initially visible
  - Creates placeholder BLEDevice and waits for passive Bluetooth discovery
  - Allows RSSI sensor and other entities to work once device is found
- **Unit test fixes**: Updated tests for new HA Bluetooth API and mocked BleakClient

## [1.8.1] - 2025-12-16

### Added
- **Expert Mode Service** `beurer_daylight_lamps.send_raw_command`
  - Send raw BLE commands directly from Home Assistant UI
  - Supports hex format: `33 01 1E` or `33011E`
  - Perfect for reverse engineering Timer/Sunrise features
  - Check logs for responses

## [1.8.0] - 2025-12-16

### Added
- **New Entity Types**:
  - **Button entities**:
    - "Identify" - Blinks the lamp 3 times to find it
    - "Reconnect" - Forces a BLE reconnection
  - **Select entity**: "Effect" dropdown for choosing light effects
  - **Number entities**:
    - "White brightness" slider (0-100%)
    - "Color brightness" slider (0-100%)
  - **Binary sensors**:
    - "Connected" - Shows BLE connection status
    - "Bluetooth reachable" - Shows if device is seen by any adapter
- **Service `beurer_daylight_lamps.apply_preset`**: Apply predefined lighting presets
  - `daylight_therapy` - Full brightness 5300K for therapy
  - `relax` - Warm dim light (2700K, 40%)
  - `focus` - Cool bright light (5000K, 90%)
  - `reading` - Neutral white (4000K, 80%)
  - `warm_cozy` - Very warm (2700K, 60%)
  - `cool_bright` - Cool white full brightness
  - `sunset` - Orange sunset simulation
  - `night_light` - Very dim warm light
  - `energize` - Bright cool light to wake up
- **BLE Sniffer Tool**: `tools/ble_sniffer.py` for reverse engineering protocol
  - Interactive command mode
  - Logs all BLE traffic to CSV
  - Probe function for discovering unknown commands

## [1.7.1] - 2025-12-16

### Added
- **Color Temperature support**: Adjustable color temperature from 2700K (warm white) to 6500K (cool daylight)
  - Uses RGB simulation to achieve color temperature values
  - Slider in Home Assistant UI for easy adjustment
  - `color_temp_kelvin` property for automations

### Fixed
- **Brightness preserves color mode**: Adjusting brightness no longer switches from RGB to white mode
- **Color changes preserve brightness**: Changing color now keeps the current brightness level

## [1.7.0] - 2025-12-16

### Added
- **Passive Bluetooth listening**: Continuously receives advertisements from the lamp
  - Real-time RSSI updates without connecting
  - Automatic adapter switching to best available proxy
  - `async_register_callback` for device presence tracking
- **Unavailability detection**: Automatic notification when device is no longer seen
  - `async_track_unavailable` marks device unavailable after ~5 minutes
  - Proper availability state in Home Assistant
- **New BeurerInstance methods**:
  - `update_ble_device()` - Switch to better Bluetooth adapter dynamically
  - `mark_seen()` / `mark_unavailable()` - Track device presence
  - `ble_available` property - Check if device is seen by any adapter
  - `last_seen` property - Timestamp of last advertisement
- **Enhanced diagnostics**: Shows `ble_available`, `last_seen` timestamp

### Changed
- **Improved availability logic**: Device must be both seen by BLE and have status

### Fixed
- Better Shelly Bluetooth Proxy support through passive listening

## [1.6.8] - 2025-12-16

### Changed
- **Full HA Bluetooth stack integration**: Now uses Home Assistant's Bluetooth APIs everywhere
  - Supports ESPHome Bluetooth Proxies for extended range
  - Uses `async_ble_device_from_address` to find best available adapter
  - Automatically routes through nearest proxy with best signal
  - No more direct BleakScanner usage - all through HA's coordinated stack
- **Removed `get_device()` function**: Replaced by HA Bluetooth APIs

### Fixed
- Devices should now be reachable via Bluetooth Proxies throughout the house

## [1.6.7] - 2025-12-16

### Changed
- **Improved config flow**: Faster device setup with better UX
  - Device list now shows RSSI signal strength (e.g. "TL100 (-60 dBm)")
  - Device name auto-fills when selecting from list
  - Uses cached BLE device during validation (no re-scan needed)
  - RSSI saved from discovery for diagnostics

## [1.6.6] - 2025-12-16

### Changed
- **Enhanced logging**: Much more detailed connection logging to help diagnose BLE issues
  - Shows device name, address, and RSSI during connection attempts
  - Logs service/characteristic discovery count
  - More specific error messages with error types and errno codes

## [1.6.5] - 2025-12-16

### Changed
- **Improved discovery**: Now uses Home Assistant's Bluetooth stack instead of custom BLE scan for device discovery
- **Code cleanup**: Removed unused `discover()` and `_has_beurer_characteristics()` functions

### Fixed
- **Faster manual setup**: Device list in config flow now uses already-discovered devices from HA's continuous scan

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
