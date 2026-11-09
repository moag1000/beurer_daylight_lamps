"""Every entity translation key has an icon in icons.json."""

import json
from pathlib import Path

import pytest

from custom_components.beurer_daylight_lamps import (
    binary_sensor,
    button,
    number,
    select,
    sensor,
    switch,
)

ICONS = json.loads(
    (
        Path(__file__).parent.parent
        / "custom_components"
        / "beurer_daylight_lamps"
        / "icons.json"
    ).read_text(encoding="utf-8")
)

DESCRIPTIONS = {
    "binary_sensor": binary_sensor.BINARY_SENSOR_DESCRIPTIONS
    + binary_sensor.THERAPY_BINARY_SENSOR_DESCRIPTIONS,
    "button": button.BUTTON_DESCRIPTIONS,
    "number": number.NUMBER_DESCRIPTIONS + number.WL90_NUMBER_DESCRIPTIONS,
    "select": select.SELECT_DESCRIPTIONS,
    "sensor": sensor.SENSOR_DESCRIPTIONS
    + sensor.THERAPY_SENSOR_DESCRIPTIONS
    + sensor.CONNECTION_HEALTH_SENSOR_DESCRIPTIONS,
    "switch": tuple(switch.SWITCH_DESCRIPTIONS + switch.DEVICE_SWITCH_DESCRIPTIONS),
}


@pytest.mark.parametrize(
    ("platform", "key"),
    [
        (platform, desc.translation_key)
        for platform, descs in DESCRIPTIONS.items()
        for desc in descs
    ],
)
def test_description_has_icon(platform: str, key: str) -> None:
    """Icons live in icons.json, not in the entity descriptions."""
    assert key in ICONS["entity"][platform]
    assert ICONS["entity"][platform][key]["default"].startswith("mdi:")


@pytest.mark.parametrize(
    ("platform", "key"),
    [
        ("number", "timer"),
        ("number", "therapy_goal"),
        ("select", "therapy_user"),
        ("switch", "alarm_1"),
        ("switch", "alarm_2"),
        ("switch", "alarm_3"),
    ],
)
def test_class_entities_have_icon(platform: str, key: str) -> None:
    """Entities without descriptions also have an icon."""
    assert ICONS["entity"][platform][key]["default"].startswith("mdi:")


def test_services_have_icons() -> None:
    """Every service in services.yaml has an icon."""
    services = (
        Path(__file__).parent.parent
        / "custom_components"
        / "beurer_daylight_lamps"
        / "services.yaml"
    ).read_text(encoding="utf-8")
    names = [
        line[:-1]
        for line in services.splitlines()
        if line and not line.startswith((" ", "#")) and line.endswith(":")
    ]
    assert names
    for name in names:
        assert name in ICONS["services"], name
