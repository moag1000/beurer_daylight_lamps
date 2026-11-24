"""Check that every raised error renders a complete message.

A translation whose placeholders differ from the ones the code passes makes
Home Assistant show a raw key or a broken message instead of the error (the
command_failed message used {devices} while the code passed {name}).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from custom_components.beurer_daylight_lamps.exceptions import (
    BeurerConnectionError,
    BeurerError,
    BeurerNotSupportedError,
    BeurerWriteError,
)

COMPONENT = Path(__file__).parent.parent / "custom_components" / "beurer_daylight_lamps"
TRANSLATION_FILES = [
    COMPONENT / "strings.json",
    *sorted((COMPONENT / "translations").glob("*.json")),
]

ERRORS: list[BeurerError] = [
    BeurerConnectionError("Lamp", "AA:BB:CC:DD:EE:FF"),
    BeurerWriteError("Lamp"),
    BeurerNotSupportedError("Lamp"),
]
# Raised as HomeAssistantError/ServiceValidationError in __init__.py
SERVICE_ERRORS = {
    "command_failed": {"devices"},
    "no_target_entities": set(),
    "invalid_hex_command": {"error"},
}


def _placeholders(message: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", message))


@pytest.mark.parametrize("path", TRANSLATION_FILES, ids=lambda p: p.name)
def test_error_placeholders_match_translations(path: Path) -> None:
    """Each message only uses placeholders its error passes."""
    exceptions = json.loads(path.read_text(encoding="utf-8"))["exceptions"]
    expected = {
        err.translation_key: set(err.translation_placeholders or {}) for err in ERRORS
    } | SERVICE_ERRORS
    for key, placeholders in expected.items():
        assert key in exceptions, f"{path.name}: missing {key}"
        assert _placeholders(exceptions[key]["message"]) <= placeholders, (
            f"{path.name}: {key}"
        )
