# Beurer TL100 Daylight Lamp - ESPHome Bluetooth Proxy Integration

This repository contains ESPHome configurations for connecting Beurer TL100 daylight therapy lamps to Home Assistant via Bluetooth Proxy.

## The Problem

The Beurer TL100 daylight lamp uses Bluetooth Low Energy (BLE) for control via the "Beurer LightUp" app. When trying to connect via ESPHome's Bluetooth Proxy, the connection fails with:

```
ESP_GATTC_DISCONNECT_EVT, reason 0x3e
```

Error `0x3e` = `BLE_HCI_CONN_FAILED_ESTABLISH` - the BLE link layer connection could not be established.

## Root Cause

After extensive debugging (analyzing btsnoop logs, comparing with Raspberry Pi's BlueZ stack, testing multiple ESP32 variants), we discovered:

**The Beurer TL100 does NOT support BLE 5.0 PHY negotiation.**

When the ESP32 tries to negotiate BLE 5.0 features (2M PHY, Coded PHY, etc.), the TL100 fails to respond properly, causing the connection to fail at the link layer level.

## The Solution

Disable BLE 5.0 features in the ESP-IDF sdkconfig:

```yaml
esp32:
  framework:
    type: esp-idf
    version: recommended
    sdkconfig_options:
      CONFIG_BT_BLE_50_FEATURES_SUPPORTED: n
      CONFIG_BT_BLE_42_FEATURES_SUPPORTED: y
```

This forces the ESP32 to use BLE 4.2 only, which the TL100 supports.

## Hardware Compatibility

| ESP32 Variant | Architecture | Cores | TL100 Compatible | Notes |
|---------------|--------------|-------|------------------|-------|
| **ESP32-S3** | Xtensa LX7 | Dual | ✅ **YES** | Recommended |
| ESP32-WROOM | Xtensa LX6 | Dual | ⚠️ Untested | Should work (BLE 4.2 native) |
| ESP32-C3 | RISC-V | Single | ❌ **NO** | Fails even with BLE 5.0 disabled |
| ESP32-C6 | RISC-V | Single | ❌ **NO** | Fails even with BLE 5.0 disabled |

### Hinweis zu ESP32-C3 und ESP32-C6

In unseren Tests konnten ESP32-C3 und ESP32-C6 als **Bluetooth Proxy** keine stabile Verbindung zur TL100 aufbauen (Fehler `0x3e`), auch mit deaktiviertem BLE 5.0.

Der Grund ist vermutlich die WiFi/BLE-Koexistenz auf dem Single-Core RISC-V - beide Protokolle konkurrieren um Ressourcen und das Timing für die BLE-Verbindung wird gestört.

**Hinweis:** Das interne Bluetooth von Home Assistant (z.B. auf einem Raspberry Pi) funktioniert problemlos mit der TL100. Das Problem betrifft nur ESPHome Bluetooth Proxies auf C3/C6.

### Anforderungen an den Bluetooth Proxy

Der Proxy muss **aktive GATT-Verbindungen** unterstützen (`active: true`). Geräte die nur passives BLE-Scanning unterstützen, funktionieren nicht:

- ❌ **Shelly Bluetooth Steckdosen** - Unterstützen kein GATT-Proxying
- ❌ **Passive BLE Scanner** - Können keine bidirektionale Verbindung aufbauen
- ✅ **ESPHome Bluetooth Proxy** mit `bluetooth_proxy: active: true`

**Empfehlung:** ESP32-S3 (oder ESP32-WROOM) für die Beurer TL100 verwenden.

## Working Configuration (ESP32-S3)

```yaml
# btproxy-beurer-s3.yaml
esphome:
  name: btproxy-beurer-s3
  friendly_name: BT Proxy Beurer S3

esp32:
  board: esp32-s3-devkitc-1
  variant: esp32s3
  framework:
    type: esp-idf
    version: recommended
    sdkconfig_options:
      # CRITICAL: Disable BLE 5.0 for TL100 compatibility
      CONFIG_BT_BLE_50_FEATURES_SUPPORTED: n
      CONFIG_BT_BLE_42_FEATURES_SUPPORTED: y

      # WiFi/BLE Coexistence
      CONFIG_SW_COEXIST_ENABLE: y
      CONFIG_SW_COEXIST_PREFERENCE_BT: y

      # BLE Connection Parameters
      CONFIG_BT_ACL_CONNECTIONS: "3"
      CONFIG_BT_GATT_MAX_SR_PROFILES: "8"

      # Pin BT to Core 0
      CONFIG_BT_BLUEDROID_PINNED_TO_CORE: "0"

logger:
  level: DEBUG

api:
  encryption:
    key: "YOUR_API_KEY_HERE"

ota:
  - platform: esphome
    password: "YOUR_OTA_PASSWORD"

wifi:
  ssid: "YOUR_WIFI_SSID"
  password: "YOUR_WIFI_PASSWORD"
  power_save_mode: none

  ap:
    ssid: "Btproxy-S3 Fallback"
    password: "fallback123"

captive_portal:

esp32_ble:

esp32_ble_tracker:
  scan_parameters:
    interval: 60ms
    window: 30ms
    active: true
    continuous: true

bluetooth_proxy:
  active: true
  cache_services: false
```

## TL100 Device Information

From our analysis:

- **Advertised Address:** `57:4C:42:50:F3:3D` (Public Address)
- **Address Type:** `0x00` (Public, not Random)
- **Bonding:** Not required (connects without pairing)
- **GATT Services:** Standard BLE services + proprietary Beurer service

## TL100 GATT Protocol

Reverse-engineered durch btsnoop HCI-Log Analyse der Beurer LightUp App:

### GATT Characteristics

| Characteristic | UUID | Purpose |
|----------------|------|---------|
| Write | `8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3` | Send commands to lamp |
| Read/Notify | `0734594a-a8e7-4b1a-a6b1-cd5243059a57` | Receive status updates |

### Command Protocol

Packets follow the format:
```
[0xFE, 0xEF, 0x0A, length+7, 0xAB, 0xAA, length+2, ...message..., checksum, 0x55, 0x0D, 0x0A]
```

### Available Commands

| Command | Bytes | Description |
|---------|-------|-------------|
| Request Status | `0x30, 0x01` or `0x30, 0x02` | Poll lamp state (white/RGB) |
| Set White Brightness | `0x31, 0x01, <0-100>` | Daylight intensity (10 levels) |
| Set Color Brightness | `0x31, 0x02, <0-100>` | Moodlight intensity |
| Set RGB Color | `0x32, <R>, <G>, <B>` | Set moodlight color |
| Set Effect | `0x34, <0-10>` | Set color effect |
| Turn Off White | `0x35, 0x01` | Deactivate daylight mode |
| Turn Off Color | `0x35, 0x02` | Deactivate moodlight mode |
| Turn On White | `0x37, 0x01` | Activate daylight therapy mode |
| Turn On Color | `0x37, 0x02` | Activate RGB moodlight mode |
| **Set Timer** | `0x3E, <minutes>` | Set auto-off timer (1-240 min, RGB mode only) |

### Supported Effects

0=Off, 1=Random, 2=Rainbow, 3=Rainbow Slow, 4=Fusion, 5=Pulse, 6=Wave, 7=Chill, 8=Action, 9=Forest, 10=Summer

### Integration Status

Unsere eigene **beurer_daylight_lamps** Integration (in diesem Repository) unterstützt:
- ✅ On/Off control (White and Color modes)
- ✅ Brightness control (separate für White und RGB)
- ✅ RGB color selection (moodlight mode)
- ✅ Color effects (11 effects)
- ✅ **Timer functionality** (1-240 Minuten, nur im RGB-Modus)
- ✅ Therapy Goal Tracking (tägliches Licht-Expositionsziel)

Alternative: [ha-beurer](https://github.com/Deadolus/ha-beurer) HACS Integration (ohne Timer-Support)

## Debugging Tips

### Check if BLE 5.0 is the issue:

1. Monitor ESPHome logs for `0x3e` errors
2. If you see repeated `ESP_GATTC_DISCONNECT_EVT, reason 0x3e`, it's likely a BLE 5.0 PHY issue
3. Add `CONFIG_BT_BLE_50_FEATURES_SUPPORTED: n` and rebuild

### Verify connection works:

Successful connection looks like:
```
[I][esp32_ble_client:111]: [0] [57:4C:42:50:F3:3D] 0x00 Connecting
[I][esp32_ble_client:318]: [0] [57:4C:42:50:F3:3D] Connection open
[I][esp32_ble_client:422]: [0] [57:4C:42:50:F3:3D] Service discovery complete
[D][esp32_ble_client:197]: ESP_GATTC_WRITE_CHAR_EVT
[D][esp32_ble_client:197]: ESP_GATTC_NOTIFY_EVT
```

Failed connection looks like:
```
[I][esp32_ble_client:111]: [0] [57:4C:42:50:F3:3D] 0x00 Connecting
[D][esp32_ble_client:354]: ESP_GATTC_DISCONNECT_EVT, reason 0x3e
```

## What We Tried (and didn't work)

1. **Adjusting connection intervals** (7.5ms → 30-50ms → 10ms) - No effect
2. **Adding IRK for address resolution** - Not needed (TL100 uses public address)
3. **NimBLE stack parameters** - No effect on C3/C6
4. **Different scan parameters** - No effect
5. **WiFi/BLE coexistence tuning** - Helped stability but didn't fix 0x3e

## Home Assistant Integration

Nach der Installation der **beurer_daylight_lamps** Integration aus diesem Repository:

1. Kopiere `custom_components/beurer_daylight_lamps/` nach `config/custom_components/`
2. Starte Home Assistant neu
3. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen**
4. Suche nach "Beurer Daylight" oder warte auf Auto-Discovery
5. Die TL100 erscheint als Licht mit:
   - White Brightness Slider
   - Color Brightness Slider
   - Timer Number (1-240 min, nur im RGB-Modus verfügbar)
   - Therapy Goal Number (tägliches Expositionsziel)

## Files in this Repository

### ESPHome Bluetooth Proxy Configs (esphome/)
- `btproxy-beurer-example.yaml` - **Template** - Copy and add your secrets.yaml
- Private configs (not in repo, use example as template):
  - `btproxy-beurer-s3.yaml` - ESP32-S3 configuration (recommended)
  - `btproxy-beurer-wroom32.yaml` - ESP32-WROOM configuration
  - `btproxy-beurer.yaml` - ESP32-C3 (doesn't work with TL100)
  - `btproxy-beurer-c6.yaml` - ESP32-C6 (doesn't work with TL100)

### Home Assistant Integration (custom_components/beurer_daylight_lamps/)
- `beurer_daylight_lamps.py` - BLE communication und Protokoll-Implementierung
- `light.py` - Home Assistant Light Entity
- `number.py` - Brightness Slider, Timer, Therapy Goal
- `sensor.py` - Status Sensoren
- `const.py` - Protokoll-Konstanten (inkl. `CMD_TIMER = 0x3E`)

### Tools (tools/)
- `timer_probe.py` - Werkzeug zum Testen von Timer-Befehlen
- `send_command.py` - Raw BLE Command Sender
- `ble_sniffer.py` - BLE Paket-Analyse

## References

- [ESPHome Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy.html)
- [ESP-IDF BLE Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/index.html)
- [BLE Error Codes](https://www.bluetooth.com/specifications/specs/core-specification-5-3/) - See Vol 1, Part F
- [ha-beurer HACS Integration](https://github.com/Deadolus/ha-beurer) - Home Assistant integration for Beurer TL100
- [Beurer TL100 Manual](https://www.manualslib.com/manual/3743846/Beurer-Tl-100.html)

## Credits

Debugging performed December 2025 using:
- btsnoop HCI log analysis from Beurer LightUp Android app
- Raspberry Pi BlueZ stack comparison
- ESPHome 2025.12.0
- ESP-IDF 5.x

---

**TL;DR:** Use ESP32-S3 with `CONFIG_BT_BLE_50_FEATURES_SUPPORTED: n` for Beurer TL100.
