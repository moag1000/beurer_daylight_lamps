# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.26.0] - 2026-01-22

### Added

- **Adaptive Polling Interval**: Polling frequency now adjusts based on device state
  - 30 seconds when light is on (responsive updates)
  - 5 minutes when light is off (save resources)
  - 15 minutes when device unavailable (minimal polling)
  - State transitions are logged for debugging
  - Reduces unnecessary BLE traffic and battery consumption

- **Connection Health Metrics**: New diagnostic sensors for monitoring BLE stability
  - `reconnect_count` - Total reconnections since startup (diagnostic)
  - `command_success_rate` - Percentage of successful BLE commands (diagnostic)
  - `connection_uptime` - Seconds since current connection established (diagnostic)
  - All disabled by default, enable via entity settings if needed
  - Includes `total_commands` as extra attribute on success rate sensor

- **Color Temperature Persistence**: Color temperature is now restored after Home Assistant restart
  - Uses `RestoreEntity` to persist color temp across restarts
  - Important since color temp is simulated via RGB and not stored on device
  - Includes new `BeurerLightExtraStoredData` dataclass for storage

- **Improved Service Error Feedback**: Services now raise `ServiceValidationError` with translations
  - Raw command failures show which devices failed
  - Invalid hex commands show the parsing error
  - No target entities shows a clear error message
  - All messages are translatable via `strings.json`

- **Therapy Tracker Public API**: Added `has_active_session` property
  - Replaces internal `_current_session is None` checks
  - Cleaner public API for checking if therapy is being tracked

### Fixed

- **Sunrise/Sunset Simulation Stability**: Fixed simulations overwhelming the BLE device
  - Created new `set_color_with_brightness_fast()` method with minimal overhead
  - Skips redundant mode switches, effect clears, and status requests
  - Only sends MODE/EFFECT commands once at start instead of every step
  - Reduces BLE commands from ~5 per step to ~2 per step
  - Adds final status request only at simulation end
  - Should significantly reduce connection drops during morning routines

- **Timer Limit Inconsistency**: Service schema now correctly limits timer to 120 minutes
  - Previously schema allowed 240 but device only supports 120
  - Now validates at service level matching the BLE protocol specification

- **Therapy Goal Validation Logging**: Now logs warning when goal is clamped to valid range
  - Helps users understand when their input was adjusted
  - Shows both original and clamped values

### Changed

- **Sunrise/Sunset Task Tracking**: Now uses `hass.async_create_background_task()`
  - Proper lifecycle management by Home Assistant
  - Better error tracking and cleanup
  - Task names include MAC address for identification

- **Optimized Initial Connect**: Removed unnecessary 2-second delay when device not visible
  - Sleep only happens when device is initially available
  - Faster startup for devices that are powered off

- **Refactored BLE Device Lookup**: Consolidated duplicate lookup code into `_get_ble_device_and_rssi()` helper
  - Reduces code duplication in `async_setup_entry()` and callbacks
  - Consistent behavior for connectable/non-connectable device lookup

### Technical Details

New constants in `const.py`:
- `POLL_INTERVAL_LIGHT_ON` (30s) - Polling when light is on
- `POLL_INTERVAL_LIGHT_OFF` (300s) - Polling when light is off
- `POLL_INTERVAL_UNAVAILABLE` (900s) - Polling when device unavailable

New properties in `beurer_daylight_lamps.py`:
- `reconnect_count` - Total reconnections since startup
- `command_success_rate` - Percentage of successful commands
- `connection_uptime_seconds` - Seconds since connection established
- `total_commands` - Total commands sent

New class in `sensor.py`:
- `BeurerConnectionHealthSensor` - Diagnostic sensor for connection metrics

New methods in `coordinator.py`:
- `_get_adaptive_interval()` - Calculates appropriate polling interval
- `_adjust_polling_interval()` - Adjusts interval based on state
- `current_poll_interval` property - Exposes current interval
- `poll_state` property - Exposes current polling state

New translations added to `strings.json`:
- `no_target_entities` - When service has no valid target
- `invalid_hex_command` - When raw command parsing fails
- `command_failed` - Updated to include device list
- `reconnect_count` - Reconnection count sensor name
- `command_success_rate` - Command success rate sensor name
- `connection_uptime` - Connection uptime sensor name

New class in `light.py`:
- `BeurerLightExtraStoredData` - Stores color_temp_kelvin across restarts

New method in `beurer_daylight_lamps.py`:
- `set_color_with_brightness_fast()` - Optimized for rapid sequential updates (simulations)

## [1.25.0] - 2026-01-21

### Added

- **Exponential Backoff for Reconnections**: Reconnect attempts now use exponential backoff
  - Starts at 1 second, doubles on each failure, maxes out at 60 seconds
  - Prevents overwhelming the BLE stack with rapid reconnection attempts
  - Automatically resets when connection succeeds or device becomes reachable again

- **Connection Watchdog**: Monitors connection health and detects stale connections
  - Checks every 60 seconds if data has been received
  - Forces reconnect if no data received for 5 minutes (stale connection)
  - Properly cleaned up on disconnect

- **Adapter Failure Tracking**: Intelligent rotation between Bluetooth adapters
  - Tracks which adapters failed recently (5 minute cooldown)
  - Prefers adapters that haven't failed when reconnecting
  - Falls back to cooldown adapters if all have failed

- **Reconnect Cooldown**: Prevents reconnect spam from frequent BLE advertisements
  - Minimum 30 seconds between reconnect attempts triggered by advertisements
  - Prevents queueing too many reconnect tasks

### Fixed

- **Race Condition in Reconnect Logic**: Fixed TOCTOU (Time-of-Check-Time-of-Use) race condition
  - Previously checked `lock.locked()` before acquiring, which could allow parallel reconnects
  - Now uses proper `async with lock` pattern with checks inside the lock
  - Affects `_auto_reconnect()`, `mark_seen()`, and `_on_disconnect()`

- **Watchdog Task Tracking**: Fixed memory leak where watchdog tasks were not properly tracked
  - `_safe_create_task()` now returns task reference
  - Watchdog task is now properly stored and can be cancelled on disconnect
  - Task cleanup in `finally` block ensures proper cleanup on exit

- **CancelledError Handling**: Fixed improper handling of task cancellation
  - `asyncio.CancelledError` is now properly re-raised to signal cancellation
  - Prevents tasks from hanging during Home Assistant shutdown
  - Applies to `_auto_reconnect()`, `_safe_create_task()`, and watchdog loop

### Changed

- **Logging Levels**: Adjusted logging levels for better signal-to-noise ratio
  - Routine reconnect attempts now use DEBUG level (was INFO)
  - Reconnect failures now use WARNING level (was DEBUG)
  - Successful reconnects still use INFO level

### Technical Details

New constants added to `const.py`:
- `RECONNECT_INITIAL_BACKOFF = 1.0` - Initial reconnect delay (seconds)
- `RECONNECT_MAX_BACKOFF = 60.0` - Maximum reconnect delay (seconds)
- `RECONNECT_BACKOFF_MULTIPLIER = 2.0` - Backoff multiplier on each failure
- `RECONNECT_MIN_INTERVAL = 30.0` - Minimum time between reconnect attempts
- `CONNECTION_WATCHDOG_INTERVAL = 60.0` - Watchdog check interval (seconds)
- `CONNECTION_STALE_TIMEOUT = 300.0` - Time without data before connection is stale
- `ADAPTER_FAILURE_COOLDOWN = 300.0` - Cooldown for failed adapters (seconds)

## [1.24.0] - 2026-01-09

### Fixed

- **BlueZ Notification Workaround**: Added workaround for bleak 2.0.0 regression on Linux/BlueZ
  - bleak 2.0.0 (shipped with HA 2026.1) switched from `StartNotify` to `AcquireNotify`
  - This can cause notification issues or disconnects on some BLE devices
  - Integration now uses `bluez={"use_start_notify": True}` when available (bleak >= 2.1.0)
  - Backwards compatible: Falls back to default behavior on older bleak versions
  - See [home-assistant/core#160503](https://github.com/home-assistant/core/issues/160503)

## [1.23.0] - 2026-01-09

### Added

- **Automatic Reconnect on Disconnect**: When the lamp disconnects but is still BLE-reachable, the integration now automatically attempts to reconnect
  - Prevents the lamp from staying "unavailable" when the connection drops temporarily
  - Especially useful with ESPHome Bluetooth Proxies where connections may be less stable

### Improved

- **Enhanced Diagnostic Logging**: Connection logs now include much more useful information
  - RSSI (signal strength) shown in connection attempts and success messages
  - Connection time measurement (e.g., "Connected in 24.9s")
  - Adapter name shown in connection logs
- **Better Timeout Error Messages**: Config flow connection timeout now shows:
  - Device RSSI and adapter information
  - Numbered troubleshooting steps (power cycle lamp, move closer, check connection slots, add proxy)
- **Disconnect Visibility**: Disconnect events now logged at INFO level (previously DEBUG) for better visibility

## [1.22.0] - 2025-12-27

### Added

- **Strict Typing**: Full mypy strict mode compliance
  - All 17 source files pass mypy with `strict = true`
  - Added `pyproject.toml` with mypy configuration
  - CI workflow now includes type checking

### Changed

- Improved Platinum tier compliance (strict typing now complete)

## [1.21.0] - 2025-12-27

### Added

- **Options Flow**: Configure integration settings after setup
  - Daily therapy goal (5-120 minutes)
  - Update interval (10-300 seconds)
  - Adaptive Lighting default state
- **Device Triggers**: Automation triggers for device events
  - Light turned on/off
  - Daily therapy goal reached
  - Connection lost/restored
- **German Translation**: Complete German translation for all UI elements

### Changed

- **CoordinatorEntity Pattern**: All entity classes now use CoordinatorEntity for centralized updates
- **Target-based Services**: Services now use `target` selector instead of `device_id`
  - Supports entity_id, device_id, and area_id targeting
  - Multiple lamps can be controlled with a single service call
- **Test Coverage**: Increased from 53% to 86% (477 tests)

### Improved

- Better separation of concerns between coordinator and entities
- More consistent code style across entity platforms
- Updated quality_scale.yaml with new features

## [1.14.0] - 2025-12-18

### Added - Adaptive Lighting Integration

#### New Entities
- **Switch**: `Adaptive Lighting` - Control whether Adaptive Lighting (HACS) can adjust this lamp
  - State persists across Home Assistant restarts via RestoreEntity
  - Automatically blocks Adaptive Lighting when:
    - Switch is turned off (user preference)
    - An effect is active (effects shouldn't be overridden)
    - Therapy mode is running (consistent light needed)
  - Extra state attributes show therapy mode status and current effect

#### Improvements
- Added German translations for all entity types (button, select, number, sensor, binary_sensor, switch)
- Added switch icons with state-dependent icons (brightness-auto/brightness-5)
- Platform.SWITCH added to integration platforms

### Changed
- Version bumped to 1.14.0

## [1.12.0] - 2025-12-17

### Added - Lifestyle Wellness Features

> **Important**: These features are for personal lifestyle tracking and wellness purposes only. This integration is **NOT a medical device** and should not be used for medical purposes.

#### New Services
- `beurer_daylight_lamps.start_sunrise` - Sunrise simulation with gradual brightness/color temperature increase
  - Profiles: gentle, natural, energize, therapy
  - Duration: 1-60 minutes
- `beurer_daylight_lamps.start_sunset` - Sunset simulation with gradual dimming
  - Configurable end brightness (0-100%)
  - Duration: 1-60 minutes
- `beurer_daylight_lamps.stop_simulation` - Stop any running simulation

#### New Entities
- **Sensor**: `Light exposure today` - Track bright light exposure in minutes
- **Sensor**: `Light exposure this week` - Weekly exposure tracking
- **Sensor**: `Daily goal progress` - Percentage of daily goal completed
- **Number**: `Daily light goal` - Configurable goal (5-120 minutes)
- **Binary Sensor**: `Daily goal reached` - True when goal is met

#### Quality & Developer Experience
- Added `diagnostics.py` - Comprehensive troubleshooting data download
- Added `repairs.py` - UI-guided repair flows for connection issues
- Added `quality_scale.yaml` - Self-documentation of compliance status
- Enhanced translations with repair flow messages
- Test suite with 126 tests (53% coverage)

### Changed
- Updated README.md with comprehensive documentation
- Added Data Updates & Communication section
- Expanded Known Limitations section (7 items)
- Added automation blueprints documentation

### Fixed
- Improved error handling in therapy tracking module

## [1.11.0] - 2025-12-17

### Added
- **Therapy Module Architecture**: `therapy.py` for wellness tracking
- **Sunrise/Sunset Engine**: Integration-layer simulation controller

## [1.10.0] - 2025-12-17

### Added
- **Timer-Funktion**: Auto-Off Timer (1-240 Minuten) via BLE-Protokoll
  - Neuer Service `beurer_daylight_lamps.set_timer`
  - Neue Number-Entity "Timer" mit Slider (1-240 min)
  - Timer nur im RGB-Modus verfügbar (Entity zeigt "unavailable" im White-Modus)
  - Timer-Kommando (0x3E) wurde durch Reverse Engineering entdeckt
- **Android BLE Sniffing Dokumentation**: CONTRIBUTING.md erweitert mit btsnooz.py Anleitung
- **Protokoll-Dokumentation**: Timer-Befehl in docs/PROTOCOL.md dokumentiert

### Changed
- Version auf 1.10.0 erhöht (Minor-Release wegen neuer Funktionalität)

## [1.9.6] - 2025-12-17

### Added
- **Heartbeat Counter Sensor**: Neuer Diagnose-Sensor zählt ACK/Heartbeat-Pakete
  - Hilft beim Monitoring der BLE-Verbindungsqualität
  - `state_class: total_increasing` für Statistiken
  - Standardmäßig deaktiviert (Entity-Registry)

### Fixed
- **Heartbeat-Pakete markieren Gerät als verfügbar**: Wenn nur Heartbeats empfangen werden, wird das Gerät jetzt korrekt als "available" markiert
- **Test-Fixes für Notification-Parsing**: Tests setzen jetzt korrekt das payload_len Byte (Position 6)

## [1.9.5] - 2025-12-17

### Fixed
- **Kritisch: Lampe wurde fälschlich als "aus" angezeigt**
  - Kurze ACK/Heartbeat-Pakete (payload_len < 8) wurden als Status interpretiert
  - Diese Pakete haben Version 0xFF was als "OFF" galt
  - Jetzt werden kurze Pakete ignoriert für State-Updates (nur Diagnostik)
- PROTOCOL.md: Paketstruktur-Dokumentation erweitert

## [1.9.4] - 2025-12-17

### Fixed
- **send_raw_command Service Logging**: Logs erscheinen jetzt als WARNING statt INFO
  - Alle RAW_CMD Logs sind nun ohne Debug-Modus sichtbar
  - Zeigt Device-Name, MAC, Verbindungsstatus und Ergebnis

## [1.9.3] - 2025-12-17

### Fixed
- **HomeKit/Siri "Kaltweiß" aktiviert jetzt White-Modus**:
  - Erkennt weiß-ähnliche RGB-Werte (alle >= 200, max Differenz 55) und nutzt nativen White-Modus
  - Siri "Kaltweiß" sendet RGB statt Farbtemperatur - wird jetzt korrekt behandelt
- **Effect wird jetzt immer zurückgesetzt beim Farbwechsel**:
  - Behebt Bug wo Rainbow/Forest Effect aktiv blieb obwohl Farbe gesetzt wurde
  - Effect wird nur zurückgesetzt wenn er nicht bereits "Off" ist (weniger BLE-Commands)

### Changed
- PROTOCOL.md: Dokumentiert Magic-Byte-Unterschied zwischen Commands (AB AA) und Responses (AB BB)

## [1.9.2] - 2025-12-17

### Added
- **Diagnostic Sensors für Reverse Engineering** (standardmäßig deaktiviert):
  - `Last raw notification` - Alle BLE-Notifications als Hex-String mit Historie
  - `Last unknown notification` - Nur Notifications mit unbekannten Version-Bytes
  - `Last notification version` - Das Version-Byte der letzten Notification
- **CONTRIBUTING.md erweitert**: Dokumentation für Entwickler zum Reverse Engineering neuer Features
- **PROTOCOL.md erweitert**: Anleitung zur Nutzung des `send_raw_command` Service über die HA UI

### Changed
- Unknown Notifications werden jetzt gespeichert statt nur geloggt (kein Log-Spam mehr)
- Notification-Handler speichert Raw-Daten für Diagnose-Sensoren

## [1.9.1] - 2025-12-17

### Added
- **HomeKit/Siri Weiß-Modus Unterstützung**: Farbtemperaturen >= 5000K aktivieren jetzt den nativen Weiß-Modus
  - In Apple Home: Farbtemperatur-Slider ganz nach "kalt" (rechts) schieben → Weiß-Modus
  - Mit Siri: "Hey Siri, stelle die Beurer Lampe auf kaltweiß" → Weiß-Modus
  - Der native Weiß-Modus bietet optimiertes 5300K Tageslicht für die Lichttherapie
- **Threshold konfigurierbar**: `WHITE_MODE_THRESHOLD_KELVIN = 5000` (kann bei Bedarf angepasst werden)

### Changed
- **Verbesserte color_mode Property**: Gibt jetzt korrekt WHITE zurück wenn der native Modus aktiv ist

## [1.9.0] - 2025-12-17

### Fixed
- **Moduswechsel führt nicht mehr zu falschen Helligkeiten/Farben**
  - Neue `set_color_with_brightness()` Methode setzt Farbe und Helligkeit atomar
  - Keine Race Conditions mehr zwischen Farb- und Helligkeitsänderungen
  - Modus wird nur gewechselt wenn wirklich nötig
- **Effect wird nur zurückgesetzt wenn nötig**: Beim Wechsel zu RGB wird Effect nur auf "Off" gesetzt wenn vorher ein anderer Effect aktiv war
- **Brightness-Änderungen wechseln nicht mehr ungewollt den Modus**
  - Brightness im RGB-Modus bleibt im RGB-Modus
  - Brightness im White-Modus bleibt im White-Modus
  - Color-Temp-Modus (simuliert) wird korrekt erkannt

### Changed
- **Vereinfachte light.py Logik**: Klarere Trennung zwischen Farbtemperatur, RGB-Farbe, Effect und reiner Helligkeit
- **Weniger BLE-Befehle**: Kein unnötiges `turn_on()` mehr, Moduswechsel direkt in den Methoden

## [1.8.11] - 2025-12-17

### Changed
- **HA wählt den besten Adapter automatisch**: Vereinfachte Verbindungslogik
  - Nutzt `async_ble_device_from_address` - HA wählt den besten Adapter mit freien Slots
  - `ble_device_callback` holt bei jedem Retry ein frisches Device von HA
  - Wenn ein Adapter keine Slots hat, wählt HA beim nächsten Retry automatisch einen anderen
  - Kein manuelles Iterieren durch Adapter mehr nötig
- **Logging zeigt Adapter-Wechsel**: "HA switched adapter: X -> Y" wenn HA einen anderen Proxy wählt

## [1.8.10] - 2025-12-17

### Fixed
- **Schnelleres Adapter-Fallback**: 15 Sekunden Timeout pro Adapter statt 45s gesamt
  - Bei "no connection slot" Fehler wird sofort der nächste Adapter probiert
  - Timeout verhindert Hängenbleiben bei nicht-reagierenden Proxies
- **Besseres Scanner-Logging**: Zeigt `source` (Adapter-MAC) statt Gerätenamen
  - Debug-Logging für Scanner-Details (source, name, adapter, type)

## [1.8.9] - 2025-12-17

### Added
- **Multi-Proxy Fallback**: Wenn ein Bluetooth Proxy keine freien Verbindungs-Slots hat, wird automatisch der nächste probiert
  - Nutzt `async_scanner_devices_by_address` um ALLE Adapter/Proxies zu finden die das Gerät sehen
  - Besonders nützlich für Shelly Plug Bluetooth Gateways (nur 1-2 Slots)
  - Log zeigt alle verfügbaren Adapter und welcher erfolgreich verbunden hat
  - Klare Fehlermeldung wenn kein Adapter freie Slots hat

### Changed
- **Verbesserte Verbindungslogik**: Probiert jeden verfügbaren Adapter nacheinander
  - Weniger Retry-Versuche pro Adapter (2 statt 5), aber mehr Adapter werden probiert
  - Schnellerer Wechsel zum nächsten Proxy bei "no connection slot" Fehlern

## [1.8.8] - 2025-12-17

### Fixed
- **Verbindung auch bei "non-connectable" Geräten versuchen**: ESPHome Proxies können manchmal auch non-connectable Geräte erreichen
  - Fallback auf ANY device wenn kein connectable gefunden
  - Bessere Log-Meldungen mit Hinweisen zur Problemlösung
- **ble_device_callback verbessert**: Versucht erst connectable, dann any device

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
