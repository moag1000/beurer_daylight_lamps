# PR und Release Anleitung für v1.8.3

## ✅ Status

- ✅ Code committed (3 Commits)
- ✅ Zum Branch gepusht: `claude/fix-bluetooth-discovery-lvihP`
- ✅ PR-Beschreibung vorbereitet → `PR_DESCRIPTION.md`
- ✅ Release-Notes vorbereitet → `RELEASE_NOTES_v1.8.3.md`

## 📝 Schritt 1: Pull Request erstellen

### Option A: Via Web-UI (Einfachste Methode)

1. **Gehen Sie zur PR-Erstellungsseite:**
   ```
   https://github.com/moag1000/beurer_daylight_lamps/pull/new/claude/fix-bluetooth-discovery-lvihP
   ```

2. **Titel verwenden:**
   ```
   Fix: Bluetooth discovery for non-connectable devices (v1.8.3)
   ```

3. **Beschreibung kopieren:**
   - Öffnen Sie `PR_DESCRIPTION.md`
   - Kopieren Sie den gesamten Inhalt
   - Fügen Sie ihn in das Beschreibungsfeld ein

4. **PR erstellen:**
   - Klicken Sie auf "Create pull request"

### Option B: Via gh CLI (Falls installiert)

```bash
gh pr create \
  --title "Fix: Bluetooth discovery for non-connectable devices (v1.8.3)" \
  --body-file PR_DESCRIPTION.md \
  --base main \
  --head claude/fix-bluetooth-discovery-lvihP
```

## 🔄 Schritt 2: PR mergen

Nach Review und Approval:

1. **Auf GitHub:**
   - Gehen Sie zum erstellten PR
   - Klicken Sie auf "Merge pull request"
   - Bestätigen Sie den Merge

2. **Lokal synchronisieren:**
   ```bash
   git checkout main
   git pull origin main
   ```

## 🏷️ Schritt 3: Release erstellen

### Option A: Via Web-UI

1. **Gehen Sie zur Release-Seite:**
   ```
   https://github.com/moag1000/beurer_daylight_lamps/releases/new
   ```

2. **Tag erstellen:**
   - Tag: `v1.8.3`
   - Target: `main` (nach dem Merge!)

3. **Release-Informationen:**
   - Title: `v1.8.3 - Fix Bluetooth Discovery for Non-Connectable Devices`
   - Description: Kopieren Sie den Inhalt aus `RELEASE_NOTES_v1.8.3.md`

4. **Release veröffentlichen:**
   - ✅ Set as the latest release
   - Klicken Sie auf "Publish release"

### Option B: Via gh CLI

```bash
gh release create v1.8.3 \
  --title "v1.8.3 - Fix Bluetooth Discovery for Non-Connectable Devices" \
  --notes-file RELEASE_NOTES_v1.8.3.md \
  --target main
```

### Option C: Via Git + GitHub API

```bash
# Tag lokal erstellen
git tag -a v1.8.3 -m "v1.8.3 - Fix Bluetooth Discovery for Non-Connectable Devices"

# Tag pushen
git push origin v1.8.3

# Dann auf GitHub das Release erstellen (Web-UI)
```

## 🎯 Schritt 4: HACS Aktualisierung

HACS erkennt das neue Release automatisch innerhalb von ~30 Minuten.

### Manueller HACS Update (für schnelleres Update):

1. In Home Assistant → HACS → Integrationen
2. Beurer Daylight Therapy Lamps → ⋮ → "Redownload"
3. Oder warten Sie auf automatische Erkennung

## 📊 Zusammenfassung der Änderungen

### Commits im PR:
```
d59dbd6 - fix: Include non-connectable devices in discovery list
03d1c8f - fix: Improve support for non-connectable BLE advertisements
a108494 - fix: v1.8.3 - Support discovery of devices with non-connectable advertisements
```

### Dateien geändert:
- `manifest.json` (Version + Bluetooth Matcher)
- `config_flow.py` (Discovery-Liste + Fallback)
- `__init__.py` (Setup + Passive Listening)
- `beurer_daylight_lamps.py` (Connection Handling)

### Statistik:
- **4 Dateien** geändert
- **110 Zeilen** hinzugefügt/modifiziert
- **0 Breaking Changes**

## ✅ Checkliste

- [ ] PR erstellt
- [ ] PR reviewed (optional)
- [ ] PR gemerged
- [ ] Tag v1.8.3 erstellt
- [ ] Release v1.8.3 veröffentlicht
- [ ] HACS zeigt neue Version (nach ~30 Min)

## 🐛 Bei Problemen

Falls Fragen auftreten:
1. Prüfen Sie die Logs: `PR_DESCRIPTION.md` und `RELEASE_NOTES_v1.8.3.md`
2. Commits überprüfen: `git log --oneline origin/main..claude/fix-bluetooth-discovery-lvihP`
3. Branch-Status: `git status`

## 📞 Support

- **Repository**: https://github.com/moag1000/beurer_daylight_lamps
- **Issues**: https://github.com/moag1000/beurer_daylight_lamps/issues
