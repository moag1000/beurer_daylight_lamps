<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/moag1000/beurer_daylight_lamps/main/docs/images/sunrise-lamp-dark.png">
    <img src="https://raw.githubusercontent.com/moag1000/beurer_daylight_lamps/main/docs/images/sunrise-lamp.png" alt="Tageslichtlampe mit Sonnenaufgang" width="160">
  </picture>
</p>

# Beurer Tageslicht-Therapielampen

🇬🇧 [English version](README.md) · Die englische README ist die ausführliche Referenz (ESPHome-Proxy-Konfiguration, alle Dienste mit Beispielen, BLE-Protokoll).

Home-Assistant-Integration für Beurer Tageslichtlampen und Wake-up-Lights über Bluetooth Low Energy (BLE).

## Unterstützte Geräte

| Modell | Status | Hinweise |
|--------|--------|----------|
| TL100 | ✅ Getestet | Voller Funktionsumfang |
| TL50, TL70, TL80, TL90 | ⚠️ Ungetestet | Sollten funktionieren |
| WL75 | ✅ Getestet (von einem Mitwirkenden) | Wake-up-Light mit UKW-Radio, 2 Wecker (eigenes BLE-Protokoll) |
| WL90 | ⚠️ Ungetestet | Wake-up-Light mit Radio, Lautsprecher, 3 Weckern |

## Funktionen

- 💡 An/Aus, Helligkeit, RGB-Farben und Farbtemperatur (ab 5000 K mit den echten weißen LEDs der Lampe)
- ✨ Lichteffekte, getrennte Helligkeit für Weiß und Farbe, Auto-Aus-Timer
- 🌅 Sonnenaufgangs- und Sonnenuntergangs-Simulation als Dienst
- 📊 Lichttherapie-Tracking: Minuten heute und diese Woche, Tagesziel mit Fortschritt (bleibt über Neustarts erhalten)
- ⏰ WL75/WL90: Radio, Lautstärke, Wecker an/aus und Weckzeiten direkt im Dashboard
- 🔔 Lampen-Ereignisse (Timer abgelaufen, Sonnenaufgang beendet, …) als Event-Entität
- 🤖 Eigene Trigger und Bedingungen im Automations-Editor, Sprachsteuerung über Assist
- 📡 Bluetooth-Erkennung, ESPHome- und Shelly-Bluetooth-Proxys mit automatischem Adapterwechsel

## Voraussetzungen

| Komponente | Mindestversion | Hinweis |
|---|---|---|
| Home Assistant Core | **2026.9.0** | Wer noch nicht aktualisieren kann: v1.37.0 (HA 2025.12 – 2026.8) |
| Bluetooth | HA-Bluetooth-Integration | Eingebauter Adapter, ESPHome- oder Shelly-Bluetooth-Proxy |

## Installation

### HACS (empfohlen)

1. HACS bzw. den Marketplace in Home Assistant öffnen
2. Nach „Beurer Daylight Lamps“ suchen
3. Herunterladen und Home Assistant neu starten

### Manuell

Den Ordner `custom_components/beurer_daylight_lamps` in das Verzeichnis `custom_components/` deiner Home-Assistant-Konfiguration kopieren und neu starten.

## Einrichtung

1. Lampe einschalten. Home Assistant findet sie automatisch per Bluetooth.
2. In der Benachrichtigung auf „Konfigurieren“ klicken.
3. Die Lampe blinkt zur Bestätigung. Danach „Absenden“.

Alternativ: **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → „Beurer Daylight Lamps“, Lampe auswählen oder MAC-Adresse eingeben.

> Die Lampe kann nur eine Bluetooth-Verbindung gleichzeitig halten. Die Beurer-App „LightUp“ kann nicht parallel genutzt werden.

### Optionen

**Einstellungen** → **Geräte & Dienste** → **Beurer Daylight Lamps** → **Konfigurieren**:

| Option | Standard | Beschreibung |
|--------|----------|--------------|
| Tägliches Lichttherapie-Ziel | 30 min | Ziel für „Tagesziel Fortschritt“ und „Tagesziel erreicht“ (5–120 min). Gleicher Wert wie die Zahl-Entität „Tägliches Lichtziel“. |
| Adaptive Lighting standardmäßig aktivieren | an | Startzustand des Adaptive-Lighting-Schalters für neu hinzugefügte Lampen |
| Standard-Therapienutzer | – | Person, der Therapie-Sitzungen zugeordnet werden, wenn an der Lampe niemand gewählt ist |

## Entitäten

| Typ | Name | Beschreibung |
|-----|------|--------------|
| Licht | Lampe | Hauptentität mit allen Lichtfunktionen |
| Taste | Identifizieren / Neu verbinden / Uhrzeit synchronisieren | Blinken, Bluetooth neu verbinden, Uhr der Lampe stellen |
| Auswahl | Effekt | Lichteffekte |
| Zahl | Helligkeit Weiß / Farbe, Timer, Tägliches Lichtziel | |
| Sensor | Lichttherapie heute / diese Woche, Tagesziel Fortschritt | Lichttherapie-Tracking |
| Binärsensor | Verbunden, Bluetooth erreichbar, Tagesziel erreicht | |
| Ereignis | Lampen-Ereignis | Timer abgelaufen/abgebrochen, Einschlaf-Timer abgelaufen, Sonnenauf-/-untergang beendet |
| Schalter | Signalton, Überblenden, Adaptive Lighting | |

**Zusätzlich bei WL75/WL90:** Mediaplayer UKW-Radio (WL90 auch Bluetooth-Lautsprecher), Lautstärke-Regler, Schalter „Wecker 1–3“ und Uhrzeit-Entitäten „Wecker 1–3 Uhrzeit“ (WL75: 2 Wecker, WL90: 3 Wecker).

## Dienste

| Dienst | Zweck |
|--------|-------|
| `beurer_daylight_lamps.apply_preset` | Voreinstellung anwenden (z. B. `daylight_therapy`, `relax`, `focus`, `reading`) |
| `beurer_daylight_lamps.set_timer` | Auto-Aus-Timer setzen (1–120 min) |
| `beurer_daylight_lamps.start_sunrise` | Sonnenaufgang starten (Dauer, Profil `gentle`/`natural`/`energize`/`therapy`) |
| `beurer_daylight_lamps.start_sunset` | Sonnenuntergang starten (Dauer, End-Helligkeit) |
| `beurer_daylight_lamps.stop_simulation` | Laufende Simulation stoppen |
| `beurer_daylight_lamps.set_alarm` | Wecker einstellen (WL75/WL90) |
| `beurer_daylight_lamps.sync_time` | Uhr der Lampe stellen (passiert auch automatisch) |

## Automationen: Trigger und Bedingungen

Im Automations-Editor findest du unter „Beurer“ eigene Bausteine:

| Art | Name | Löst aus / prüft, wenn |
|-----|------|------------------------|
| Trigger | Lampen-Timer abgelaufen | der Auto-Aus-Timer abgelaufen ist |
| Trigger | Lampen-Timer abgebrochen | ein Timer an der Lampe abgebrochen wurde |
| Trigger | Einschlaf-Timer abgelaufen | der Radio-/Musik-Einschlaf-Timer (WL75/WL90) abgelaufen ist |
| Trigger | Sonnenaufgang / Sonnenuntergang beendet | eine Simulation fertig ist |
| Trigger | Tagesziel Lichttherapie erreicht | das Tagesziel erreicht wird |
| Bedingung | Tagesziel Lichttherapie erreicht | das Tagesziel erreicht ist |
| Bedingung | Lampe ist verbunden | die Lampe per Bluetooth verbunden ist |

```yaml
triggers:
  - trigger: beurer_daylight_lamps.sunrise_finished
    target:
      entity_id: event.schlafzimmer_lampe_lampen_ereignis
conditions:
  - condition: beurer_daylight_lamps.is_therapy_goal_reached
    target:
      entity_id: binary_sensor.schlafzimmer_lampe_tagesziel_erreicht
actions:
  - action: notify.mobile_app_handy
    data:
      message: "Guten Morgen, der Sonnenaufgang ist fertig."
```

## Sprachsteuerung (Assist)

Sprachassistenten mit LLM (Assist-API) bekommen Werkzeuge für Lampen, die für Assist freigegeben sind: Sonnenaufgang oder -untergang starten, Simulation stoppen und den Therapie-Status abfragen. Zum Beispiel: „Starte einen 20-minütigen Sonnenaufgang im Schlafzimmer“ oder „Habe ich heute mein Lichtziel erreicht?“

## Blueprints

Fertige Automations-Vorlagen in [`blueprints/automation/beurer_daylight_lamps/`](blueprints/automation/beurer_daylight_lamps/):

- **Morning Light Therapy**: Sonnenaufgang zur Weckzeit, danach Lichttherapie. Endet auf Wunsch, sobald das Tagesziel erreicht ist.
- **Evening Wind Down**: Abends langsam warm und dunkel
- **Focus Work Session**: Konzentrationslicht mit optionalen Pausen

## Fehlerbehebung

- **Lampe wird nicht gefunden:** Lampe einschalten, nicht mit der Beurer-App verbunden lassen, näher an den Bluetooth-Adapter stellen oder einen ESPHome-Bluetooth-Proxy nutzen.
- **Verbindung bricht ab:** Signalstärke-Sensor aktivieren (unter -80 dBm ist es zu schwach), Proxy näher an die Lampe.
- **Entität nicht verfügbar:** Unter **Einstellungen** → **System** → **Reparaturen** nachsehen oder die Taste „Neu verbinden“ drücken.
- **Diagnose:** Integration → drei Punkte → **Diagnose herunterladen** (MAC-Adresse wird geschwärzt).

## Entfernen

**Einstellungen** → **Geräte & Dienste** → Beurer Daylight Lamps → drei Punkte → **Löschen**, danach Home Assistant neu starten. Die gespeicherte Therapie-Historie der Lampe wird dabei gelöscht.

## Danksagung

Siehe [Credits in der englischen README](README.md#credits). Danke an alle, die mit Fixes, Tests und neuen Modellen beigetragen haben.

> **Hinweis:** Lifestyle-/Wellness-Funktion, kein Medizinprodukt.
