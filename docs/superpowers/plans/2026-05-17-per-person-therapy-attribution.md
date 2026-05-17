# Per-Person Therapy Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attribute every Beurer therapy session to a Home Assistant `person`, expose per-person aggregated sensors via a virtual hub device, and emit a session event for user automations.

**Architecture:** Per-lamp `TherapyTracker` gains `person_id` on every session. Each lamp gets a `select` entity to choose the active person. A singleton "Therapy Hub" virtual device owns dynamic per-person sensors that aggregate across all lamp entries. `end_session()` fires a `beurer_daylight_lamps_therapy_session` event.

**Tech Stack:** Python 3.13, Home Assistant 2026.x, pytest, pytest-homeassistant-custom-component, voluptuous.

**Spec:** `docs/superpowers/specs/2026-05-17-per-person-therapy-attribution-design.md`

---

## File Map

- Modify: `custom_components/beurer_daylight_lamps/therapy.py` — `person_id` on `TherapySession`; `start_session/end_session` plumb it.
- Modify: `custom_components/beurer_daylight_lamps/const.py` — new constants.
- Modify: `custom_components/beurer_daylight_lamps/beurer_daylight_lamps.py` — auto-trigger reads select; event fired on session end.
- Modify: `custom_components/beurer_daylight_lamps/config_flow.py` — options-flow gets `default_therapy_user`.
- Modify: `custom_components/beurer_daylight_lamps/select.py` — register `BeurerTherapyUserSelect`.
- Modify: `custom_components/beurer_daylight_lamps/__init__.py` — register `set_therapy_user` service, manage hub singleton lifecycle.
- Modify: `custom_components/beurer_daylight_lamps/services.yaml` — `set_therapy_user` schema.
- Modify: `custom_components/beurer_daylight_lamps/strings.json` — translations for select + service.
- Modify: `custom_components/beurer_daylight_lamps/sensor.py` — wire hub sensors via setup.
- Create: `custom_components/beurer_daylight_lamps/therapy_hub.py` — `TherapyHub` singleton.
- Modify: `tests/test_therapy.py` — extend for `person_id`.
- Create: `tests/test_therapy_user.py` — select entity + service.
- Create: `tests/test_therapy_hub.py` — hub aggregation, lifecycle, event.

---

## Task 1: TherapySession gets person_id

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/therapy.py:82-99`
- Test: `tests/test_therapy.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_therapy.py`:

```python
from datetime import UTC, datetime

from custom_components.beurer_daylight_lamps.therapy import TherapySession


def test_session_stores_person_id() -> None:
    session = TherapySession(
        start_time=datetime.now(tz=UTC),
        person_id="person.michael",
    )
    assert session.person_id == "person.michael"


def test_session_person_id_defaults_none() -> None:
    session = TherapySession(start_time=datetime.now(tz=UTC))
    assert session.person_id is None
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy.py::test_session_stores_person_id -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'person_id'`.

- [ ] **Step 3: Add field**

Edit `therapy.py:82-99`, add field after `brightness_pct`:

```python
@dataclass
class TherapySession:
    """Tracks a single therapy session."""

    start_time: datetime
    end_time: datetime | None = None
    color_temp_kelvin: int = 5300
    brightness_pct: int = 100
    person_id: str | None = None
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_therapy.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/therapy.py tests/test_therapy.py
git commit -m "feat(therapy): add person_id field to TherapySession"
```

---

## Task 2: Tracker plumbs person_id through start/end

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/therapy.py:115-166`
- Test: `tests/test_therapy.py`

- [ ] **Step 1: Add failing test**

```python
def test_tracker_records_person_on_start() -> None:
    from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

    tracker = TherapyTracker()
    tracker.start_session(
        color_temp_kelvin=5300, brightness_pct=100, person_id="person.anna"
    )
    ended = tracker.end_session()
    assert ended is not None
    assert ended.person_id == "person.anna"


def test_tracker_person_id_optional() -> None:
    from custom_components.beurer_daylight_lamps.therapy import TherapyTracker

    tracker = TherapyTracker()
    tracker.start_session(color_temp_kelvin=5300, brightness_pct=100)
    ended = tracker.end_session()
    assert ended is not None
    assert ended.person_id is None
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy.py::test_tracker_records_person_on_start -v`
Expected: FAIL — `unexpected keyword argument 'person_id'`.

- [ ] **Step 3: Plumb argument**

Replace `start_session` in `therapy.py`:

```python
def start_session(
    self,
    color_temp_kelvin: int = 5300,
    brightness_pct: int = 100,
    person_id: str | None = None,
) -> None:
    """Start tracking a new therapy session."""
    if self._current_session is not None:
        self.end_session()

    self._current_session = TherapySession(
        start_time=datetime.now(tz=UTC),
        color_temp_kelvin=color_temp_kelvin,
        brightness_pct=brightness_pct,
        person_id=person_id,
    )
    LOGGER.debug(
        "Started therapy session: %dK @ %d%% (person=%s)",
        color_temp_kelvin,
        brightness_pct,
        person_id,
    )
```

(`end_session` already returns the session; no change required there.)

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_therapy.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/therapy.py tests/test_therapy.py
git commit -m "feat(therapy): plumb person_id through start_session"
```

---

## Task 3: New constants

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/const.py`

- [ ] **Step 1: Append constants**

Append to `const.py`:

```python
# Per-person therapy attribution
CONF_DEFAULT_THERAPY_USER = "default_therapy_user"
DEFAULT_THERAPY_USER: str | None = None
THERAPY_USER_UNKNOWN = "unknown"
EVENT_THERAPY_SESSION = "beurer_daylight_lamps_therapy_session"
THERAPY_HUB_IDENTIFIER = "therapy_hub"
```

- [ ] **Step 2: Verify import path works**

Run: `python -c "from custom_components.beurer_daylight_lamps.const import EVENT_THERAPY_SESSION, THERAPY_USER_UNKNOWN, CONF_DEFAULT_THERAPY_USER, THERAPY_HUB_IDENTIFIER; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add custom_components/beurer_daylight_lamps/const.py
git commit -m "feat(therapy): add per-person attribution constants"
```

---

## Task 4: BeurerTherapyUserSelect entity

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/select.py`
- Test: `tests/test_therapy_user.py` (create)

- [ ] **Step 1: Create failing test**

Create `tests/test_therapy_user.py`:

```python
"""Tests for therapy user attribution (select + service)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.beurer_daylight_lamps.const import (
    DOMAIN,
    THERAPY_USER_UNKNOWN,
)

from .conftest import setup_integration


@pytest.mark.asyncio
async def test_therapy_user_select_created(hass: HomeAssistant) -> None:
    """Select entity for active therapy user is created per lamp."""
    await setup_integration(hass)
    registry = er.async_get(hass)
    entries = [
        e for e in registry.entities.values()
        if e.platform == DOMAIN and e.domain == "select"
        and e.unique_id.endswith("_therapy_user")
    ]
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_therapy_user_select_default_unknown(hass: HomeAssistant) -> None:
    """Default option is the 'unknown' sentinel when no persons exist."""
    await setup_integration(hass)
    state = next(
        s for s in hass.states.async_all("select")
        if s.entity_id.endswith("_therapy_user")
    )
    assert state.state == THERAPY_USER_UNKNOWN
    assert THERAPY_USER_UNKNOWN in state.attributes["options"]
```

(`setup_integration` is a helper that must exist in `tests/conftest.py`; if not, the test discovery error in step 2 surfaces that and the next step adds a minimal fallback.)

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy_user.py -v`
Expected: FAIL — entity does not exist (or import error if `setup_integration` missing).

If `setup_integration` is missing, add this minimal helper at the end of `tests/conftest.py`:

```python
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.beurer_daylight_lamps.const import DOMAIN


async def setup_integration(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"mac": "AA:BB:CC:DD:EE:FF", "name": "Test Lamp"},
        options={},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
```

- [ ] **Step 3: Add select entity**

Replace `select.py` contents:

```python
"""Select platform for Beurer Daylight Lamps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEFAULT_THERAPY_USER,
    DOMAIN,
    LOGGER,
    SUPPORTED_EFFECTS,
    THERAPY_USER_UNKNOWN,
    VERSION,
    detect_model,
)
from .coordinator import BeurerDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import BeurerConfigEntry

SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="effect",
        translation_key="effect",
        icon="mdi:palette",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeurerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer select entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    name = entry.data.get("name", "Beurer Lamp")

    entities: list[SelectEntity] = [
        BeurerEffectSelect(coordinator, name, SELECT_DESCRIPTIONS[0]),
        BeurerTherapyUserSelect(hass, coordinator, name, entry),
    ]
    async_add_entities(entities)


class BeurerEffectSelect(CoordinatorEntity[BeurerDataUpdateCoordinator], SelectEntity):
    """Representation of a Beurer effect select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        description: SelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._instance = coordinator.instance
        self._device_name = device_name
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._instance.mac)}_{description.key}"
        self._attr_options = list(SUPPORTED_EFFECTS)

    @property
    def current_option(self) -> str | None:
        return self._instance.effect

    @property
    def available(self) -> bool:
        return self._instance.available

    @property
    def device_info(self) -> DeviceInfo:
        mac = format_mac(self._instance.mac)
        return DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=detect_model(self._device_name),
            sw_version=VERSION,
            connections={(CONNECTION_BLUETOOTH, mac)},
        )

    async def async_select_option(self, option: str) -> None:
        LOGGER.debug("Setting effect to %s", option)
        await self._instance.set_effect(option)


class BeurerTherapyUserSelect(
    CoordinatorEntity[BeurerDataUpdateCoordinator], SelectEntity, RestoreEntity
):
    """Selects which HA person is currently doing therapy on this lamp."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account"
    _attr_translation_key = "therapy_user"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BeurerDataUpdateCoordinator,
        device_name: str,
        entry: BeurerConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._instance = coordinator.instance
        self._device_name = device_name
        self._entry = entry
        self._attr_unique_id = (
            f"{format_mac(self._instance.mac)}_therapy_user"
        )
        self._current: str = THERAPY_USER_UNKNOWN

    @property
    def options(self) -> list[str]:
        persons = sorted(
            s.entity_id for s in self._hass.states.async_all("person")
        )
        return [THERAPY_USER_UNKNOWN, *persons]

    @property
    def current_option(self) -> str:
        return self._current

    @property
    def device_info(self) -> DeviceInfo:
        mac = format_mac(self._instance.mac)
        return DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=self._device_name,
            manufacturer="Beurer",
            model=detect_model(self._device_name),
            sw_version=VERSION,
            connections={(CONNECTION_BLUETOOTH, mac)},
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self.options:
            self._current = last.state
        else:
            default = self._entry.options.get(CONF_DEFAULT_THERAPY_USER)
            if default and default in self.options:
                self._current = default

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError(f"Invalid therapy user: {option}")
        self._current = option
        self.async_write_ha_state()
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_therapy_user.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/select.py tests/test_therapy_user.py tests/conftest.py
git commit -m "feat(therapy): add per-lamp therapy_user select entity"
```

---

## Task 5: Auto-trigger reads select for person_id

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/beurer_daylight_lamps.py:1590-1611`
- Test: `tests/test_therapy_user.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_therapy_user.py`:

```python
@pytest.mark.asyncio
async def test_auto_session_uses_select_person(hass: HomeAssistant) -> None:
    """When the select is set to a person, auto-started session records it."""
    hass.states.async_set("person.michael", "home")
    entry = await setup_integration(hass)
    sel = next(
        s for s in hass.states.async_all("select")
        if s.entity_id.endswith("_therapy_user")
    )
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": sel.entity_id, "option": "person.michael"},
        blocking=True,
    )

    instance = entry.runtime_data.instance
    # Simulate bright cool white light to trigger auto-session
    instance._color_on = True
    instance._color_brightness = 230
    instance._rgb_color = (200, 200, 200)
    instance._track_therapy_from_rgb()
    ended = instance.therapy_tracker.end_session()

    assert ended is not None
    assert ended.person_id == "person.michael"
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy_user.py::test_auto_session_uses_select_person -v`
Expected: FAIL — `ended.person_id` is `None`.

- [ ] **Step 3: Read select in auto-trigger**

Add helper method on `BeurerInstance` (place near `_track_therapy_from_rgb`, around line 1590):

```python
def _resolve_therapy_person(self) -> str | None:
    """Resolve the active therapy person from this lamp's select entity."""
    from homeassistant.helpers import entity_registry as er
    from .const import THERAPY_USER_UNKNOWN
    registry = er.async_get(self._hass)
    mac = format_mac(self.mac)
    unique = f"{mac}_therapy_user"
    entry_id = registry.async_get_entity_id("select", "beurer_daylight_lamps", unique)
    if entry_id is None:
        return None
    state = self._hass.states.get(entry_id)
    if state is None or state.state == THERAPY_USER_UNKNOWN:
        return None
    return state.state
```

(`format_mac` is already imported in this file; if not, add `from homeassistant.helpers.device_registry import format_mac` at the top.)

Then in `_track_therapy_from_rgb`, replace the start_session line:

```python
if (
    is_white_ish
    and brightness_pct >= 80
    and not self._therapy_tracker.has_active_session
):
    self._therapy_tracker.start_session(
        estimated_kelvin,
        brightness_pct,
        person_id=self._resolve_therapy_person(),
    )
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_therapy_user.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/beurer_daylight_lamps.py tests/test_therapy_user.py
git commit -m "feat(therapy): record active person when auto-starting session"
```

---

## Task 6: Options-flow gains default_therapy_user

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/config_flow.py:576-622`
- Test: `tests/test_config_flow.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_config_flow.py`:

```python
import pytest
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.const import (
    CONF_DEFAULT_THERAPY_USER,
)
from .conftest import setup_integration


@pytest.mark.asyncio
async def test_options_flow_accepts_default_therapy_user(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set("person.michael", "home")
    entry = await setup_integration(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert CONF_DEFAULT_THERAPY_USER in result["data_schema"].schema
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DEFAULT_THERAPY_USER: "person.michael"},
    )
    assert result["type"].value == "create_entry"
    assert entry.options[CONF_DEFAULT_THERAPY_USER] == "person.michael"
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_config_flow.py::test_options_flow_accepts_default_therapy_user -v`
Expected: FAIL — `CONF_DEFAULT_THERAPY_USER` not in schema.

- [ ] **Step 3: Extend options flow**

At top of `config_flow.py`, add to imports:

```python
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)
from .const import CONF_DEFAULT_THERAPY_USER
```

In `BeurerOptionsFlowHandler.async_step_init`, add to the schema dict (after `CONF_ADAPTIVE_LIGHTING_DEFAULT`):

```python
vol.Optional(
    CONF_DEFAULT_THERAPY_USER,
    default=current_options.get(CONF_DEFAULT_THERAPY_USER),
): EntitySelector(EntitySelectorConfig(domain="person")),
```

`vol.Optional` with `default=None` will accept absence; if `vol` complains about `None` default, wrap as:

```python
vol.Optional(
    CONF_DEFAULT_THERAPY_USER,
    description={"suggested_value": current_options.get(CONF_DEFAULT_THERAPY_USER)},
): EntitySelector(EntitySelectorConfig(domain="person")),
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_config_flow.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/config_flow.py tests/test_config_flow.py
git commit -m "feat(config): add default_therapy_user to options flow"
```

---

## Task 7: set_therapy_user service

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/__init__.py`
- Modify: `custom_components/beurer_daylight_lamps/services.yaml`
- Modify: `custom_components/beurer_daylight_lamps/strings.json`
- Test: `tests/test_services.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_services.py`:

```python
import pytest
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.const import DOMAIN
from .conftest import setup_integration


@pytest.mark.asyncio
async def test_set_therapy_user_service(hass: HomeAssistant) -> None:
    hass.states.async_set("person.anna", "home")
    entry = await setup_integration(hass)
    light_state = next(
        s for s in hass.states.async_all("light")
        if s.entity_id.startswith("light.test_lamp")
    )
    await hass.services.async_call(
        DOMAIN, "set_therapy_user",
        {"entity_id": light_state.entity_id, "person": "person.anna"},
        blocking=True,
    )
    sel = next(
        s for s in hass.states.async_all("select")
        if s.entity_id.endswith("_therapy_user")
    )
    assert sel.state == "person.anna"
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_services.py::test_set_therapy_user_service -v`
Expected: FAIL — service not registered.

- [ ] **Step 3: Register service**

In `__init__.py`, add constant near other `SERVICE_*` constants:

```python
SERVICE_SET_THERAPY_USER = "set_therapy_user"
```

Add schema (place near other service schemas):

```python
SERVICE_SET_THERAPY_USER_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("person"): cv.entity_id,
    }
)
```

Inside `_async_setup_services`, register the service (place alongside other `hass.services.async_register` calls):

```python
async def _set_therapy_user(call: ServiceCall) -> None:
    light_entity_id = call.data["entity_id"]
    person = call.data["person"]
    entity_registry = er.async_get(hass)
    light_entry = entity_registry.async_get(light_entity_id)
    if light_entry is None or light_entry.platform != DOMAIN:
        raise vol.Invalid(f"{light_entity_id} is not a Beurer light entity")
    mac = light_entry.unique_id.split("_")[0]
    select_unique = f"{mac}_therapy_user"
    select_entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, select_unique
    )
    if select_entity_id is None:
        raise vol.Invalid("Therapy user select entity not found")
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": select_entity_id, "option": person},
        blocking=True,
    )


if not hass.services.has_service(DOMAIN, SERVICE_SET_THERAPY_USER):
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_THERAPY_USER,
        _set_therapy_user,
        schema=SERVICE_SET_THERAPY_USER_SCHEMA,
    )
    LOGGER.debug("Registered service %s.%s", DOMAIN, SERVICE_SET_THERAPY_USER)
```

Ensure `from homeassistant.helpers import entity_registry as er` and `import homeassistant.helpers.config_validation as cv` are imported at the top of the file (they likely already are).

- [ ] **Step 4: Append service schema to `services.yaml`**

```yaml
set_therapy_user:
  name: Set therapy user
  description: Set the active therapy user for a Beurer lamp.
  fields:
    entity_id:
      name: Lamp
      description: The Beurer light entity.
      required: true
      selector:
        entity:
          domain: light
          integration: beurer_daylight_lamps
    person:
      name: Person
      description: The HA person to attribute therapy sessions to.
      required: true
      selector:
        entity:
          domain: person
```

- [ ] **Step 5: Append translations to `strings.json`**

Under `"services"` (create if missing):

```json
"set_therapy_user": {
  "name": "Set therapy user",
  "description": "Set the active therapy user for a Beurer lamp.",
  "fields": {
    "entity_id": { "name": "Lamp", "description": "Beurer light entity." },
    "person": { "name": "Person", "description": "HA person to attribute sessions to." }
  }
}
```

Under `"entity"` → `"select"` add `"therapy_user": { "name": "Therapy user" }`.

- [ ] **Step 6: Run tests, expect PASS**

Run: `pytest tests/test_services.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add custom_components/beurer_daylight_lamps/__init__.py custom_components/beurer_daylight_lamps/services.yaml custom_components/beurer_daylight_lamps/strings.json tests/test_services.py
git commit -m "feat(therapy): add set_therapy_user service"
```

---

## Task 8: Event on session end

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/beurer_daylight_lamps.py` (call sites of `end_session`)
- Test: `tests/test_therapy_hub.py` (create)

- [ ] **Step 1: Create failing test**

Create `tests/test_therapy_hub.py`:

```python
"""Tests for therapy hub aggregation and session event."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant

from custom_components.beurer_daylight_lamps.const import EVENT_THERAPY_SESSION

from .conftest import setup_integration


@pytest.mark.asyncio
async def test_event_fired_on_session_end(hass: HomeAssistant) -> None:
    hass.states.async_set("person.michael", "home")
    entry = await setup_integration(hass)
    sel = next(
        s for s in hass.states.async_all("select")
        if s.entity_id.endswith("_therapy_user")
    )
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": sel.entity_id, "option": "person.michael"},
        blocking=True,
    )

    events: list = []
    hass.bus.async_listen(EVENT_THERAPY_SESSION, lambda e: events.append(e.data))

    instance = entry.runtime_data.instance
    instance._color_on = True
    instance._color_brightness = 230
    instance._rgb_color = (200, 200, 200)
    instance._track_therapy_from_rgb()
    # backdate start so duration >= 1 minute
    instance.therapy_tracker._current_session.start_time = (
        datetime.now(tz=UTC) - timedelta(minutes=2)
    )
    instance._color_on = False
    instance._track_therapy_from_rgb()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0]["person_id"] == "person.michael"
    assert events[0]["entry_id"] == entry.entry_id
    assert events[0]["duration_minutes"] >= 1
    assert "lamp_name" in events[0]
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy_hub.py::test_event_fired_on_session_end -v`
Expected: FAIL — no event fired.

- [ ] **Step 3: Fire event on session end**

In `beurer_daylight_lamps.py`, add a private helper on `BeurerInstance` (near `_track_therapy_from_rgb`):

```python
def _end_therapy_and_emit(self) -> None:
    """End the active session and fire the per-person event if any."""
    from .const import EVENT_THERAPY_SESSION
    session = self._therapy_tracker.end_session()
    if session is None or session.end_time is None:
        return
    self._hass.bus.async_fire(
        EVENT_THERAPY_SESSION,
        {
            "entry_id": self._entry.entry_id,
            "lamp_name": self._device_name,
            "person_id": session.person_id,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat(),
            "duration_minutes": round(session.duration_minutes, 1),
            "color_temp_kelvin": session.color_temp_kelvin,
            "brightness_pct": session.brightness_pct,
        },
    )
```

If `BeurerInstance` does not already keep references to `entry` and `device_name`, audit the constructor; both are passed into `_create_instance` (`__init__.py:389`). If missing, store them as `self._entry = entry` and `self._device_name = device_name` in `__init__` and update `_create_instance` to pass them.

Replace every call to `self._therapy_tracker.end_session()` in this file with `self._end_therapy_and_emit()` (two locations: `_track_therapy_from_rgb` at the `elif not self._color_on` branch, and `_handle_device_off`).

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_therapy_hub.py::test_event_fired_on_session_end -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/beurer_daylight_lamps.py tests/test_therapy_hub.py
git commit -m "feat(therapy): emit session event on end_session"
```

---

## Task 9: TherapyHub singleton + virtual device

**Files:**
- Create: `custom_components/beurer_daylight_lamps/therapy_hub.py`
- Modify: `custom_components/beurer_daylight_lamps/__init__.py` (init/cleanup hub)

- [ ] **Step 1: Add failing test**

Append to `tests/test_therapy_hub.py`:

```python
@pytest.mark.asyncio
async def test_hub_device_created(hass: HomeAssistant) -> None:
    from homeassistant.helpers import device_registry as dr
    from custom_components.beurer_daylight_lamps.const import (
        DOMAIN, THERAPY_HUB_IDENTIFIER,
    )

    await setup_integration(hass)
    dev_reg = dr.async_get(hass)
    hub = dev_reg.async_get_device(
        identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)}
    )
    assert hub is not None
    assert hub.name == "Beurer Therapy Hub"
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy_hub.py::test_hub_device_created -v`
Expected: FAIL — hub device does not exist.

- [ ] **Step 3: Create `therapy_hub.py`**

```python
"""Singleton hub for per-person therapy aggregation across all Beurer lamps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, THERAPY_HUB_IDENTIFIER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

HUB_DATA_KEY = "therapy_hub"


class TherapyHub:
    """Singleton that owns the virtual Beurer Therapy Hub device."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.owning_entry_id: str | None = None

    def ensure_device(self, owning_entry: ConfigEntry) -> dr.DeviceEntry:
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_or_create(
            config_entry_id=owning_entry.entry_id,
            identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)},
            name="Beurer Therapy Hub",
            manufacturer="Beurer",
            model="Therapy Aggregation",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self.owning_entry_id = owning_entry.entry_id
        return device

    def remove_device(self) -> None:
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(
            identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)}
        )
        if device is not None:
            dev_reg.async_remove_device(device.id)
        self.owning_entry_id = None


def get_or_create_hub(hass: HomeAssistant) -> TherapyHub:
    domain_data = hass.data.setdefault(DOMAIN, {})
    hub = domain_data.get(HUB_DATA_KEY)
    if hub is None:
        hub = TherapyHub(hass)
        domain_data[HUB_DATA_KEY] = hub
    return hub
```

- [ ] **Step 4: Initialize hub in `async_setup_entry`**

In `__init__.py`'s `async_setup_entry`, after `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)`:

```python
from .therapy_hub import get_or_create_hub
hub = get_or_create_hub(hass)
hub.ensure_device(entry)
```

In `async_unload_entry`, after platforms are unloaded, add:

```python
from .therapy_hub import HUB_DATA_KEY, get_or_create_hub
remaining = [
    e for e in hass.config_entries.async_entries(DOMAIN)
    if e.entry_id != entry.entry_id and e.state.recoverable
]
if not remaining:
    hub = hass.data.get(DOMAIN, {}).get(HUB_DATA_KEY)
    if hub is not None:
        hub.remove_device()
        hass.data[DOMAIN].pop(HUB_DATA_KEY, None)
```

If `async_unload_entry` is not present in `__init__.py`, find it (HA convention) or add at module level. Inspect the file first; do not duplicate.

- [ ] **Step 5: Run tests, expect PASS**

Run: `pytest tests/test_therapy_hub.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/beurer_daylight_lamps/therapy_hub.py custom_components/beurer_daylight_lamps/__init__.py tests/test_therapy_hub.py
git commit -m "feat(therapy): add Therapy Hub singleton virtual device"
```

---

## Task 10: Per-person aggregation sensors

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/therapy_hub.py`
- Modify: `custom_components/beurer_daylight_lamps/sensor.py`
- Test: `tests/test_therapy_hub.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_therapy_hub.py`:

```python
@pytest.mark.asyncio
async def test_per_person_sensors_aggregate(hass: HomeAssistant) -> None:
    hass.states.async_set("person.michael", "home")
    entry = await setup_integration(hass)
    sel = next(
        s for s in hass.states.async_all("select")
        if s.entity_id.endswith("_therapy_user")
    )
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": sel.entity_id, "option": "person.michael"},
        blocking=True,
    )

    instance = entry.runtime_data.instance
    instance._color_on = True
    instance._color_brightness = 230
    instance._rgb_color = (200, 200, 200)
    instance._track_therapy_from_rgb()
    instance.therapy_tracker._current_session.start_time = (
        datetime.now(tz=UTC) - timedelta(minutes=5)
    )
    instance._color_on = False
    instance._track_therapy_from_rgb()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.beurer_therapy_today_michael")
    assert state is not None
    assert float(state.state) >= 5.0
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy_hub.py::test_per_person_sensors_aggregate -v`
Expected: FAIL — per-person sensor missing.

- [ ] **Step 3: Add aggregation helpers to hub**

Append to `therapy_hub.py`:

```python
from datetime import UTC, datetime, timedelta


def _iter_trackers(hass: HomeAssistant):
    from .const import DOMAIN
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        yield runtime.instance.therapy_tracker


def _sum_minutes_for(
    hass: HomeAssistant, person_id: str, since: datetime
) -> float:
    total = 0.0
    for tracker in _iter_trackers(hass):
        for session in tracker.sessions:
            if (
                session.person_id == person_id
                and session.is_therapy_light
                and session.start_time >= since
            ):
                total += session.duration_minutes
        cur = tracker._current_session
        if (
            cur is not None
            and cur.person_id == person_id
            and cur.is_therapy_light
            and cur.start_time >= since
        ):
            total += cur.duration_minutes
    return total


def today_minutes_for(hass: HomeAssistant, person_id: str) -> float:
    midnight = datetime.now(tz=UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return _sum_minutes_for(hass, person_id, midnight)


def week_minutes_for(hass: HomeAssistant, person_id: str) -> float:
    now = datetime.now(tz=UTC)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return _sum_minutes_for(hass, person_id, week_start)


def goal_progress_for(
    hass: HomeAssistant, person_id: str, goal_minutes: int
) -> int:
    if goal_minutes <= 0:
        return 0
    return min(100, int(today_minutes_for(hass, person_id) / goal_minutes * 100))
```

- [ ] **Step 4: Register per-person sensors in `sensor.py`**

Add this block at the bottom of `async_setup_entry` in `sensor.py` (guarded so it only runs once):

```python
from .therapy_hub import HUB_DATA_KEY, get_or_create_hub
from .const import THERAPY_HUB_IDENTIFIER, DEFAULT_THERAPY_GOAL, CONF_THERAPY_GOAL

domain_data = hass.data.setdefault(DOMAIN, {})
if domain_data.get(f"{HUB_DATA_KEY}_sensors_added"):
    return
domain_data[f"{HUB_DATA_KEY}_sensors_added"] = True

hub = get_or_create_hub(hass)
hub.ensure_device(entry)

def _person_slug(entity_id: str) -> str:
    return entity_id.split(".", 1)[1]

def _build_person_sensors() -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    for ps in hass.states.async_all("person"):
        slug = _person_slug(ps.entity_id)
        entities.extend([
            BeurerPersonTherapySensor(hass, ps.entity_id, slug, "today"),
            BeurerPersonTherapySensor(hass, ps.entity_id, slug, "week"),
            BeurerPersonTherapySensor(hass, ps.entity_id, slug, "progress"),
        ])
    return entities

async_add_entities(_build_person_sensors())
```

Add the entity class to `sensor.py`:

```python
from homeassistant.helpers.device_registry import DeviceInfo
from .const import THERAPY_HUB_IDENTIFIER, CONF_THERAPY_GOAL, DEFAULT_THERAPY_GOAL
from .therapy_hub import (
    today_minutes_for, week_minutes_for, goal_progress_for,
)


class BeurerPersonTherapySensor(SensorEntity):
    """Aggregated therapy sensor for one HA person across all lamps."""

    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        person_entity_id: str,
        slug: str,
        kind: str,
    ) -> None:
        self._hass = hass
        self._person = person_entity_id
        self._kind = kind
        self._attr_unique_id = f"therapy_{kind}_{slug}"
        self._attr_translation_key = f"therapy_{kind}_person"
        if kind == "progress":
            self._attr_native_unit_of_measurement = "%"
        else:
            self._attr_native_unit_of_measurement = "min"
        self._attr_name = {
            "today": f"Therapy today {slug}",
            "week": f"Therapy week {slug}",
            "progress": f"Therapy progress {slug}",
        }[kind]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, THERAPY_HUB_IDENTIFIER)},
            name="Beurer Therapy Hub",
            manufacturer="Beurer",
            model="Therapy Aggregation",
        )

    @property
    def native_value(self) -> float | int:
        if self._kind == "today":
            return round(today_minutes_for(self._hass, self._person), 1)
        if self._kind == "week":
            return round(week_minutes_for(self._hass, self._person), 1)
        goal = self._first_goal()
        return goal_progress_for(self._hass, self._person, goal)

    def _first_goal(self) -> int:
        for entry in self._hass.config_entries.async_entries(DOMAIN):
            return int(entry.options.get(CONF_THERAPY_GOAL, DEFAULT_THERAPY_GOAL))
        return DEFAULT_THERAPY_GOAL
```

- [ ] **Step 5: Run test, expect PASS**

Run: `pytest tests/test_therapy_hub.py::test_per_person_sensors_aggregate -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/beurer_daylight_lamps/therapy_hub.py custom_components/beurer_daylight_lamps/sensor.py tests/test_therapy_hub.py
git commit -m "feat(therapy): per-person aggregation sensors on hub"
```

---

## Task 11: React to person registry add/remove

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/sensor.py`
- Test: `tests/test_therapy_hub.py`

- [ ] **Step 1: Add failing test**

```python
@pytest.mark.asyncio
async def test_per_person_sensor_added_when_new_person_appears(
    hass: HomeAssistant,
) -> None:
    await setup_integration(hass)
    assert hass.states.get("sensor.beurer_therapy_today_anna") is None

    hass.states.async_set("person.anna", "home")
    await hass.async_block_till_done()
    # Hub watches person state changes via state-added events
    await hass.async_block_till_done()

    assert hass.states.get("sensor.beurer_therapy_today_anna") is not None
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `pytest tests/test_therapy_hub.py::test_per_person_sensor_added_when_new_person_appears -v`
Expected: FAIL — sensor not added dynamically.

- [ ] **Step 3: Listen for new person entities**

In `sensor.py`'s `async_setup_entry`, after the initial `async_add_entities(_build_person_sensors())` call, add:

```python
from homeassistant.helpers.event import async_track_state_added_domain

known_persons: set[str] = {
    s.entity_id for s in hass.states.async_all("person")
}

@callback
def _handle_new_person(event) -> None:
    new_id = event.data["entity_id"]
    if new_id in known_persons:
        return
    known_persons.add(new_id)
    slug = _person_slug(new_id)
    async_add_entities([
        BeurerPersonTherapySensor(hass, new_id, slug, "today"),
        BeurerPersonTherapySensor(hass, new_id, slug, "week"),
        BeurerPersonTherapySensor(hass, new_id, slug, "progress"),
    ])

unsub = async_track_state_added_domain(hass, "person", _handle_new_person)
entry.async_on_unload(unsub)
```

Ensure `from homeassistant.core import callback` is imported.

- [ ] **Step 4: Run tests, expect PASS**

Run: `pytest tests/test_therapy_hub.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/beurer_daylight_lamps/sensor.py tests/test_therapy_hub.py
git commit -m "feat(therapy): dynamically add sensors when new person is created"
```

---

## Task 12: Translations + CHANGELOG

**Files:**
- Modify: `custom_components/beurer_daylight_lamps/strings.json`
- Modify: `custom_components/beurer_daylight_lamps/translations/de.json`
- Modify: `CHANGELOG.md`
- Modify: `custom_components/beurer_daylight_lamps/manifest.json` (version bump)

- [ ] **Step 1: Add German translations**

In `translations/de.json`, mirror new keys added to `strings.json` in Task 7 (services + select). Translate:
- `"therapy_user"` name → `"Therapie-Person"`
- service description → `"Setzt die aktive Therapie-Person für eine Beurer-Lampe."`
- field descriptions → German equivalents
- Add per-person sensor keys (`therapy_today_person`, `therapy_week_person`, `therapy_progress_person`) with German names.

- [ ] **Step 2: Add CHANGELOG entry**

At the top of `CHANGELOG.md` under a new version header (next minor bump, e.g. `## v1.36.0`):

```markdown
### Added
- Per-person therapy attribution: select entity per lamp to choose the active person.
- New "Beurer Therapy Hub" virtual device with per-person aggregated sensors (today/week/progress).
- Service `beurer_daylight_lamps.set_therapy_user` for setting the active person from automations.
- Event `beurer_daylight_lamps_therapy_session` fired on session end with full payload.
- Options-flow field `default_therapy_user`.
```

- [ ] **Step 3: Bump version**

In `manifest.json`, increment `"version"` per semver (next minor). Match in `const.py`'s `VERSION` if defined there.

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Run hassfest / HACS validation locally if available**

Run: `python -m script.hassfest --integration-path custom_components/beurer_daylight_lamps` (skip if hassfest is not installed locally — CI will catch it).

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md custom_components/beurer_daylight_lamps/strings.json custom_components/beurer_daylight_lamps/translations/de.json custom_components/beurer_daylight_lamps/manifest.json
git commit -m "chore: translations, changelog, version bump for per-person therapy"
```

---

## Self-Review Notes

- Spec coverage: data model (Task 1), select per lamp (Task 4), options default (Task 6), service (Task 7), event (Task 8), hub singleton (Task 9), per-person sensors (Task 10), dynamic person handling (Task 11), edge cases tested in Task 5 + 8 + 10. All spec sections mapped.
- Backwards compatibility: existing per-lamp sensors untouched; `person_id` defaults to `None`.
- Tests: each task adds at least one failing test before implementation, in line with TDD.
- File creation: `therapy_hub.py` only created when its first test demands it (Task 9).

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-05-17-per-person-therapy-attribution.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch with checkpoints.

Which approach?
