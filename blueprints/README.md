# Beurer Daylight Lamps - Blueprints

Ready-to-use automation blueprints for your Beurer daylight therapy lamp.

## Quick Install

Click any badge below to import directly into Home Assistant:

| Blueprint | Description | Install |
|-----------|-------------|---------|
| **Morning Light Therapy** | Wake up with sunrise simulation + therapy session | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmoag1000%2Fbeurer_daylight_lamps%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbeurer_daylight_lamps%2Fmorning_light_therapy.yaml) |
| **Evening Wind Down** | Gradual dimming for better sleep | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmoag1000%2Fbeurer_daylight_lamps%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbeurer_daylight_lamps%2Fevening_wind_down.yaml) |
| **Focus Work Session** | Alerting light with Pomodoro breaks | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmoag1000%2Fbeurer_daylight_lamps%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fbeurer_daylight_lamps%2Ffocus_work_session.yaml) |

## Manual Installation

1. Download the YAML file(s) from [`automation/beurer_daylight_lamps/`](automation/beurer_daylight_lamps/)
2. Copy to your Home Assistant config:
   ```
   config/blueprints/automation/beurer_daylight_lamps/
   ```
3. Restart Home Assistant or reload automations

## Blueprint Details

### Morning Light Therapy

Simulates a natural sunrise followed by bright light therapy.

**Features:**
- Gradual sunrise simulation (2700K → 5300K)
- Configurable sunrise duration (0-30 min)
- Therapy session at full brightness
- Schedule: workdays, weekends, or daily
- End options: off, stay on, or reading light
- Multi-light sync support

**Recommended settings:**
- Sunrise: 15-20 minutes
- Therapy: 20-30 minutes

---

### Evening Wind Down

Gradually dims to warm light to prepare for sleep.

**Features:**
- Warm light only (2700K) - no blue light
- Trigger at sunset or fixed time
- Configurable dimming duration (15-120 min)
- Option to only run if lamp is already on
- Multi-light sync support

**Recommended settings:**
- Start 1-2 hours before bedtime
- Duration: 30-60 minutes

---

### Focus Work Session

Sets alerting cool light for concentration.

**Features:**
- Cool light (4000K-6500K)
- Optional Pomodoro break reminders
- Configurable session duration
- End options: relax light, off, or stay on
- Multi-light sync support

**Recommended settings:**
- Color temperature: 5000K
- Session: 60 minutes
- Pomodoro breaks: every 25 minutes

## Multi-Light Support

All blueprints support syncing additional lights with your Beurer lamp:

| Sync Mode | Behavior |
|-----------|----------|
| **Full sync** | Match brightness AND color temperature |
| **Brightness only** | Follow brightness, keep original color |
| **On/Off only** | Turn on/off together, use default settings |

Compatible with any Home Assistant light entity (WiZ, Hue, WLED, etc.)

## Requirements

- [Beurer Daylight Lamps](https://github.com/moag1000/beurer_daylight_lamps) integration installed
- At least one Beurer lamp configured

## Troubleshooting

**Blueprint not appearing after import?**
- Go to Settings → Automations & Scenes → Blueprints
- Click the reload button (top right)

**Automation not running?**
- Check if the lamp entity is available
- Verify the schedule/trigger settings
- Check Home Assistant logs for errors

**Lights not syncing?**
- Ensure additional lights support color temperature (for full sync)
- Try "brightness only" mode for RGB-only lights

## Support

- [Integration Documentation](https://github.com/moag1000/beurer_daylight_lamps)
- [Report Issues](https://github.com/moag1000/beurer_daylight_lamps/issues)
