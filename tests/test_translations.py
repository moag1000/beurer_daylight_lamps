"""Translations stay complete and in sync with the code.

Home Assistant loads custom integrations' texts from translations/*.json,
never from strings.json. en.json had fallen 83 keys behind strings.json and
de.json 53, so entities such as the FM radio, the speaker and three
connection sensors showed no name, and the set_alarm service had no UI text.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

COMPONENT = Path(__file__).parent.parent / "custom_components" / "beurer_daylight_lamps"
STRINGS = COMPONENT / "strings.json"
TRANSLATIONS = sorted((COMPONENT / "translations").glob("*.json"))
PLATFORMS = (
    "binary_sensor",
    "button",
    "event",
    "light",
    "media_player",
    "number",
    "select",
    "sensor",
    "switch",
    "text",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(node: dict[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in node.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", text))


def test_english_translation_is_strings_json() -> None:
    """strings.json is the source; en.json is what Home Assistant shows."""
    assert _load(COMPONENT / "translations" / "en.json") == _load(STRINGS)


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda p: p.name)
def test_translation_complete(path: Path) -> None:
    """Every text exists and uses the same placeholders as the source."""
    source = _flatten(_load(STRINGS))
    translated = _flatten(_load(path))
    assert sorted(set(source) - set(translated)) == []
    assert sorted(set(translated) - set(source)) == []
    wrong = [
        key
        for key, text in source.items()
        if _placeholders(text) != _placeholders(translated[key])
    ]
    assert wrong == []


def _entity_translation_keys(platform: str) -> set[str]:
    """translation_key values set in a platform module."""
    module = COMPONENT / f"{platform}.py"
    if not module.exists():
        return set()
    keys: set[str] = set()
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if (isinstance(node, ast.keyword) and node.arg == "translation_key") or (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_attr_translation_key"
        ):
            value = node.value
        else:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            keys.add(value.value)
    return keys


@pytest.mark.parametrize("platform", PLATFORMS)
def test_entity_names_exist(platform: str) -> None:
    """An entity whose translation_key has no text shows up without a name."""
    entities = _load(STRINGS).get("entity", {}).get(platform, {})
    missing = sorted(_entity_translation_keys(platform) - set(entities))
    assert missing == []


def test_service_fields_match_services_yaml() -> None:
    """Service fields in the UI are exactly the ones the services accept."""
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text("utf-8"))
    texts = _load(STRINGS)["services"]
    assert set(texts) == set(services)
    for name, service in services.items():
        fields = set((service or {}).get("fields") or {})
        assert set(texts[name].get("fields", {})) == fields, name
