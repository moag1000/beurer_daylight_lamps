# Per-Person Therapy Attribution

**Status:** Draft
**Date:** 2026-05-17

## Problem

Therapy session tracking is lamp-scoped. In multi-person HA setups there is no way to know which person completed a session. Sensors `therapy_today` / `therapy_week` / `therapy_progress` aggregate all users on a lamp.

## Goals

- Attribute each therapy session to a Home Assistant `person` entity.
- Expose per-person aggregated sensors across all lamps.
- Emit an event per session so users can build custom automations / logbook entries.
- Backwards compatible: existing per-lamp sensors keep working.

## Non-Goals

- Long-term persistence beyond HA Recorder (no `.storage` JSON).
- Detection heuristics (no zone / presence guessing).
- Per-lamp × per-person sensor matrix.

## Design

### 1. Data Model

`TherapySession` gains an optional `person_id` field (HA `person.*` entity_id, or `None` for unattributed).

```python
@dataclass
class TherapySession:
    start_time: datetime
    end_time: datetime | None = None
    color_temp_kelvin: int = 5300
    brightness_pct: int = 100
    person_id: str | None = None
```

`TherapyTracker` stays per-lamp. `start_session(...)` accepts `person_id`. `end_session()` stamps the session and returns it for hub aggregation + event emission.

### 2. Per-Lamp Entities

For each config entry:

- **`select.beurer_<lamp>_therapy_user`** — options: all `person.*` entity_ids + `"unknown"`. State persisted via RestoreEntity. Default value sourced from options-flow.

Options-flow gains `default_therapy_user` (entity selector, domain `person`, default `None`).

Existing auto-session trigger (`beurer_daylight_lamps.py:1608`) reads the select state when calling `start_session()`.

New service for manual override:

```yaml
beurer_daylight_lamps.set_therapy_user:
  fields:
    entity_id:
      selector:
        entity:
          domain: light
          integration: beurer_daylight_lamps
    person:
      selector:
        entity:
          domain: person
```

Service writes to the select-entity (single source of truth).

### 3. Hub Entities + Events

**Virtual device** `Beurer Therapy Hub` — singleton, `identifiers={(DOMAIN, "therapy_hub")}`. First config entry to load creates it; ownership transfers if the owning entry is unloaded while others remain. Cleanup when last entry unloads.

**Sensors per HA `person`** (dynamic — listens to `person` registry add/remove and reconciles entities):

| Sensor | Value |
|---|---|
| `sensor.beurer_therapy_today_<person>` | Minutes today, summed across all lamps |
| `sensor.beurer_therapy_week_<person>` | Minutes this week, summed across all lamps |
| `sensor.beurer_therapy_progress_<person>` | % of daily goal |

Aggregation: hub iterates `hass.data[DOMAIN]` → all entry trackers → filters `session.person_id == person_id`. State refreshed on every `end_session` and on a 60 s tick while any session is active.

Existing per-lamp sensors (`sensor.beurer_<lamp>_therapy_*`) keep their current behaviour (lamp total, all users).

**Event** — fired on every `end_session()`:

```python
hass.bus.async_fire("beurer_daylight_lamps_therapy_session", {
    "entry_id": entry.entry_id,
    "lamp_name": device_name,
    "person_id": session.person_id,          # None if unknown
    "start_time": session.start_time.isoformat(),
    "end_time": session.end_time.isoformat(),
    "duration_minutes": round(session.duration_minutes, 1),
    "color_temp_kelvin": session.color_temp_kelvin,
    "brightness_pct": session.brightness_pct,
})
```

## Edge Cases

- **`person_id` references deleted person** → session retains the stale id, per-person sensor ignores it, event still fires.
- **No `person` entities in HA** → select offers only `"unknown"`, no per-person sensors are created.
- **Lamp entry unloaded mid-session** → tracker keeps the session until end, then it is discarded (current behaviour, unchanged).
- **Two lamps active for two persons simultaneously** → each lamp has its own select, attribution independent.

## Backwards Compatibility

- `TherapySession.person_id` defaults to `None`; existing trackers continue to work.
- Existing per-lamp sensors unchanged.
- New entities appear after upgrade; no migration required.

## Testing

- `tests/test_therapy_user.py` — Session creation with / without `person_id`, select state read by auto-trigger, service override path.
- `tests/test_therapy_hub.py` — Aggregation across multiple entries, person add/remove during runtime, event payload shape, hub device lifecycle.
- Extend `tests/test_options_flow.py` with `default_therapy_user` field.

## Open Questions

None.
