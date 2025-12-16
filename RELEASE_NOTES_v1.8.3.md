# v1.8.3 - Fix Bluetooth Discovery for Non-Connectable Devices

## 🐛 Bug Fix Release

Behebt kritische Discovery-Probleme bei Beurer TL-Geräten, die non-connectable Bluetooth-Advertisements senden.

## Problem

Einige Beurer TL-Geräte (insbesondere TL100) wurden im Home Assistant Bluetooth-Monitor erkannt, aber:
- ❌ Erschienen nicht in der Integrations-Discovery-Liste
- ❌ Konnten nicht über die UI eingerichtet werden
- ❌ Zeigten "Device not found" Fehler bei manueller Einrichtung

Dies betraf Geräte, die zwischen connectable und non-connectable Advertisement-Modi wechseln oder dauerhaft im non-connectable Modus senden.

## Lösung

### 1️⃣ Manifest Discovery
- Entfernung des `"connectable": true` Filters aus allen Bluetooth-Matchern
- Integration wird jetzt für alle Advertisement-Typen angeboten

### 2️⃣ Device Discovery
- Explizites Abrufen von connectable UND non-connectable Geräten
- Intelligente Deduplizierung (bevorzugt connectable Version)
- Verbesserte Debug-Logs für Troubleshooting

### 3️⃣ Connection Handling
- Fallback-Logik bei Device-Lookups
- Versucht erst Standard, dann explizit `connectable=False`
- Robustere Verbindungserkennung

## Was ist neu?

### ✨ Features
- 🔍 **Vollständige Non-Connectable Support**: Geräte mit non-connectable Advertisements werden überall unterstützt
- 📊 **Debug-Logging**: Detaillierte Statistiken über gefundene Geräte
- 🔄 **Fallback-Mechanismus**: Automatischer Fallback bei Device-Lookups

### 🔧 Technische Details
```python
# Vorher (nur connectable)
discovered = async_discovered_service_info(hass)

# Nachher (beide Typen)
discovered_connectable = async_discovered_service_info(hass, connectable=True)
discovered_non_connectable = async_discovered_service_info(hass, connectable=False)
all_discovered = merge_and_deduplicate(...)
```

## 📊 Änderungen

- **4 Dateien** geändert
- **110 Zeilen** hinzugefügt/modifiziert
- **3 Commits** mit logischer Aufteilung

### Betroffene Komponenten
- ✅ `manifest.json` - Bluetooth Matcher
- ✅ `config_flow.py` - Discovery & Setup
- ✅ `__init__.py` - Entry Setup & Passive Listening
- ✅ `beurer_daylight_lamps.py` - Connection Handling

## 🧪 Getestet mit

- ✅ TL100 (non-connectable Advertisements)
- ✅ TL50, TL70, TL80, TL90 (verschiedene Modi)
- ✅ ESPHome Bluetooth Proxies
- ✅ Native Bluetooth-Adapter
- ✅ Mehrere gleichzeitige Geräte

## 📝 Breaking Changes

**Keine!** Alle Änderungen sind rückwärtskompatibel.

Bestehende Installationen funktionieren ohne Änderungen weiter.

## 📥 Installation

### Via HACS (empfohlen)
1. HACS → Integrationen
2. Beurer Daylight Therapy Lamps → Update auf v1.8.3
3. Home Assistant neu starten

### Manuell
1. Dateien nach `custom_components/beurer_daylight_lamps/` kopieren
2. Home Assistant neu starten
3. Integration über UI einrichten

## 🔍 Debug-Logging aktivieren

Für erweiterte Diagnose:

```yaml
logger:
  default: info
  logs:
    custom_components.beurer_daylight_lamps: debug
```

**Beispiel-Output:**
```
Found 15 connectable and 3 non-connectable devices, 18 total unique
Found Beurer device: TL100_F33D (57:4C:42:50:F3:3D) RSSI: -73, connectable: False
Device not found without filter, trying connectable=False...
```

## 🐛 Bekannte Probleme

Keine bekannten Probleme in dieser Version.

## 📚 Weitere Informationen

- **Dokumentation**: https://github.com/moag1000/beurer_daylight_lamps
- **Issues**: https://github.com/moag1000/beurer_daylight_lamps/issues
- **Diskussionen**: GitHub Discussions

## 🙏 Credits

Dank an alle Community-Mitglieder, die dieses Problem gemeldet und beim Testen geholfen haben!

---

**Vollständiges Changelog**: [v1.8.2...v1.8.3](https://github.com/moag1000/beurer_daylight_lamps/compare/v1.8.2...v1.8.3)
