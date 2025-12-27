"""Exceptions for Beurer Daylight Lamps integration.

This module provides translatable exceptions for better error handling
following Home Assistant best practices (Gold tier requirement).
"""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class BeurerError(HomeAssistantError):
    """Base exception for Beurer integration errors.

    All Beurer-specific errors should inherit from this class.
    Uses translation keys from strings.json for localized messages.
    """

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
    """Error when connection to device fails."""

    def __init__(self, name: str, mac: str | None = None) -> None:
        """Initialize connection error.

        Args:
            name: Device name for error message
            mac: Optional MAC address
        """
        placeholders = {"name": name}
        if mac:
            placeholders["mac"] = mac
        super().__init__(
            translation_key="connection_failed",
            translation_placeholders=placeholders,
        )


class BeurerDeviceNotFoundError(BeurerError):
    """Error when device cannot be found via Bluetooth."""

    def __init__(self, name: str, mac: str) -> None:
        """Initialize device not found error.

        Args:
            name: Device name
            mac: MAC address
        """
        super().__init__(
            translation_key="device_not_found",
            translation_placeholders={"name": name, "mac": mac},
        )


class BeurerCommandError(BeurerError):
    """Error when a command fails to send."""

    def __init__(self, name: str) -> None:
        """Initialize command error.

        Args:
            name: Device name
        """
        super().__init__(
            translation_key="command_failed",
            translation_placeholders={"name": name},
        )


class BeurerWriteError(BeurerError):
    """Error when BLE write operation fails."""

    def __init__(self, name: str) -> None:
        """Initialize write error.

        Args:
            name: Device name
        """
        super().__init__(
            translation_key="write_failed",
            translation_placeholders={"name": name},
        )


class BeurerTimerError(BeurerError):
    """Error when timer operation fails."""

    def __init__(self, name: str, reason: str = "timer_failed") -> None:
        """Initialize timer error.

        Args:
            name: Device name
            reason: Translation key for specific timer error
        """
        super().__init__(
            translation_key=reason,
            translation_placeholders={"name": name},
        )


class BeurerDeviceUnavailableError(BeurerError):
    """Error when device is not available."""

    def __init__(self, name: str) -> None:
        """Initialize unavailable error.

        Args:
            name: Device name
        """
        super().__init__(
            translation_key="device_unavailable",
            translation_placeholders={"name": name},
        )


class BeurerReconnectError(BeurerError):
    """Error when reconnection attempts fail."""

    def __init__(self, name: str) -> None:
        """Initialize reconnect error.

        Args:
            name: Device name
        """
        super().__init__(
            translation_key="reconnect_failed",
            translation_placeholders={"name": name},
        )


class BeurerInitializationError(BeurerError):
    """Error during device initialization."""

    def __init__(self, name: str, mac: str, error: str) -> None:
        """Initialize initialization error.

        Args:
            name: Device name
            mac: MAC address
            error: Original error message
        """
        super().__init__(
            translation_key="initialization_failed",
            translation_placeholders={"name": name, "mac": mac, "error": error},
        )
