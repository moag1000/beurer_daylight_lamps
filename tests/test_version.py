"""The integration version shown in diagnostics and device info is current."""

import json
from pathlib import Path

from custom_components.beurer_daylight_lamps.const import VERSION

MANIFEST = (
    Path(__file__).parents[1] / "custom_components/beurer_daylight_lamps/manifest.json"
)


def test_version_matches_manifest() -> None:
    """const.VERSION was left at 1.38.0 for two releases (seen in #18's diagnostics)."""
    assert json.loads(MANIFEST.read_text())["version"] == VERSION
