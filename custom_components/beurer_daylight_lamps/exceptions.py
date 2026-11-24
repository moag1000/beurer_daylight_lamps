"""Exceptions for Beurer Daylight Lamps integration.

Translatable errors that reach the user (entity actions, service calls).
The messages live in the "exceptions" section of strings.json.
"""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class BeurerError(HomeAssistantError):
    """Base exception for Beurer integration errors."""

    def __init__(
        self,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize BeurerError with translation support.

        Args:
            translation_key: Key in strings.json exceptions section
            translation_placeholders: Values to substitute in the message
        """
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders or {},
        )


class BeurerConnectionError(BeurerError):
    """The lamp could not be connected."""

    def __init__(self, name: str, mac: str) -> None:
        """Initialize connection error."""
        super().__init__(
            translation_key="connection_failed",
            translation_placeholders={"name": name, "mac": mac},
        )


class BeurerWriteError(BeurerError):
    """A command packet could not be delivered over the BLE link."""

    def __init__(self, name: str) -> None:
        """Initialize write error."""
        super().__init__(
            translation_key="write_failed",
            translation_placeholders={"name": name},
        )


class BeurerNotSupportedError(BeurerError):
    """The lamp model does not have this function."""

    def __init__(self, name: str) -> None:
        """Initialize not-supported error."""
        super().__init__(
            translation_key="not_supported",
            translation_placeholders={"name": name},
        )


class BeurerSettingsUnknownError(BeurerError):
    """The lamp did not report its settings, so none can be changed safely."""

    def __init__(self, name: str) -> None:
        """Initialize settings-unknown error."""
        super().__init__(
            translation_key="settings_unknown",
            translation_placeholders={"name": name},
        )
