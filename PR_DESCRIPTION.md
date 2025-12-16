# Fix: Bluetooth discovery for non-connectable devices (v1.8.3)

## 🐛 Problem

Einige Beurer TL-Geräte (insbesondere TL100) wurden im Home Assistant Bluetooth-Monitor erkannt, aber nicht in der Integrations-Discovery-Liste angezeigt. Dies führte dazu, dass Benutzer ihre Geräte nicht über die UI einrichten konnten.

**Beispiel-Gerät:**
```json
{
  "name": "TL100_F33D",
  "address": "57:4C:42:50:F3:3D",
  "connectable": false,
  "service_uuids": ["00003df3-0000-1000-8000-00805f9b34fb"]
}
```

## 🔍 Ursachen-Analyse

Das Problem hatte drei Ebenen:

### 1. Manifest-Level (Bluetooth Matcher)
- **Problem:** `manifest.json` spezifizierte `"connectable": true` für alle Bluetooth-Matcher
- **Auswirkung:** Home Assistant bot die Integration nur für connectable Advertisements an
- **Lösung:** Entfernung des `connectable` Feldes → akzeptiert beide Typen

### 2. Discovery-Level (Geräte-Liste)
- **Problem:** `async_discovered_service_info()` ohne Parameter lieferte nur connectable Geräte
- **Auswirkung:** Non-connectable Geräte erschienen nicht in der Auswahlliste
- **Lösung:** Explizites Abrufen von `connectable=True` UND `connectable=False`, dann Zusammenführen

### 3. Connection-Level (Geräte-Zugriff)
- **Problem:** `async_ble_device_from_address()` ohne Parameter fand non-connectable Geräte nicht
- **Auswirkung:** "Device not found" Fehler bei Verbindungsaufbau
- **Lösung:** Fallback-Logik mit explizitem `connectable=False` Versuch

## ✨ Änderungen

### Commit 1: Basis-Support (a108494)
```diff
- Entfernung aller connectable=True Filter in Bluetooth-APIs
- Aktualisierung manifest.json (Entfernung "connectable": true)
- Version bump auf 1.8.3
```

### Commit 2: Fallback-Logik (03d1c8f)
```diff
+ Expliziter Fallback auf connectable=False bei allen Device-Lookups
+ Debug-Logging für Troubleshooting
+ Anwendung in: config_flow.py, __init__.py, beurer_daylight_lamps.py
```

### Commit 3: Discovery-Liste (d59dbd6)
```diff
+ Abrufen beider Device-Typen in async_step_user
+ Deduplizierung und Bevorzugung von connectable Version
+ Debug-Logging für Discovery-Statistiken
```

## 📊 Betroffene Dateien

| Datei | Änderungen | Beschreibung |
|-------|-----------|--------------|
| `manifest.json` | 11 Zeilen | Entfernung connectable-Filter |
| `config_flow.py` | 54 Zeilen | Discovery-Liste + Fallback |
| `__init__.py` | 26 Zeilen | Setup + Passive Listening |
| `beurer_daylight_lamps.py` | 19 Zeilen | Connection-Fallback |

## 🧪 Test-Plan

- [x] Non-connectable Geräte erscheinen in Discovery-Liste
- [x] Non-connectable Geräte können ausgewählt werden
- [x] Verbindungsaufbau funktioniert unabhängig vom Advertisement-Typ
- [x] Connectable Geräte funktionieren weiterhin (keine Regression)
- [x] Debug-Logs zeigen korrekte Statistiken

**Beispiel Debug-Output:**
```
Found 15 connectable and 3 non-connectable devices, 18 total unique
Found Beurer device: TL100_F33D (57:4C:42:50:F3:3D) RSSI: -73, connectable: False
```

## 📝 Breaking Changes

Keine. Alle Änderungen sind rückwärtskompatibel.

## 🎯 Auswirkungen

✅ **Benutzer können jetzt:**
- Alle Beurer TL-Geräte sehen, unabhängig vom Advertisement-Typ
- Geräte mit non-connectable Advertisements einrichten
- Bestehende Setups funktionieren ohne Änderungen weiter

## 🔗 Referenzen

- Issue: Gerät im Monitor sichtbar, aber nicht in Integration
- Bluetooth Advertisement Types: [BLE Spec](https://www.bluetooth.com/specifications/specs/)
- Home Assistant Bluetooth Integration: [Docs](https://www.home-assistant.io/integrations/bluetooth/)
