"""Test Beurer Daylight Lamps exceptions."""
from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.beurer_daylight_lamps.const import DOMAIN
from custom_components.beurer_daylight_lamps.exceptions import (
    BeurerError,
    BeurerConnectionError,
    BeurerDeviceNotFoundError,
    BeurerCommandError,
    BeurerWriteError,
    BeurerTimerError,
    BeurerDeviceUnavailableError,
    BeurerReconnectError,
    BeurerInitializationError,
)


# =============================================================================
# Test BeurerError Base Class
# =============================================================================


class TestBeurerError:
    """Tests for BeurerError base class."""

    def test_inheritance(self) -> None:
        """Test BeurerError inherits from HomeAssistantError."""
        error = BeurerError("test_key")
        assert isinstance(error, HomeAssistantError)

    def test_translation_domain(self) -> None:
        """Test translation domain is set correctly."""
        error = BeurerError("test_key")
        assert error.translation_domain == DOMAIN

    def test_translation_key(self) -> None:
        """Test translation key is set correctly."""
        error = BeurerError("my_error_key")
        assert error.translation_key == "my_error_key"

    def test_translation_placeholders_default(self) -> None:
        """Test translation placeholders default to empty dict."""
        error = BeurerError("test_key")
        assert error.translation_placeholders == {}

    def test_translation_placeholders_custom(self) -> None:
        """Test custom translation placeholders."""
        placeholders = {"name": "Test Device", "value": "42"}
        error = BeurerError("test_key", placeholders)
        assert error.translation_placeholders == placeholders

    def test_translation_placeholders_none_becomes_empty(self) -> None:
        """Test None placeholders become empty dict."""
        error = BeurerError("test_key", None)
        assert error.translation_placeholders == {}


# =============================================================================
# Test BeurerConnectionError
# =============================================================================


class TestBeurerConnectionError:
    """Tests for BeurerConnectionError."""

    def test_inheritance(self) -> None:
        """Test BeurerConnectionError inherits from BeurerError."""
        error = BeurerConnectionError("Test Lamp")
        assert isinstance(error, BeurerError)
        assert isinstance(error, HomeAssistantError)

    def test_translation_key(self) -> None:
        """Test translation key is connection_failed."""
        error = BeurerConnectionError("Test Lamp")
        assert error.translation_key == "connection_failed"

    def test_placeholders_name_only(self) -> None:
        """Test placeholders with name only."""
        error = BeurerConnectionError("My Lamp")
        assert error.translation_placeholders["name"] == "My Lamp"
        assert "mac" not in error.translation_placeholders

    def test_placeholders_with_mac(self) -> None:
        """Test placeholders with name and MAC."""
        error = BeurerConnectionError("My Lamp", "AA:BB:CC:DD:EE:FF")
        assert error.translation_placeholders["name"] == "My Lamp"
        assert error.translation_placeholders["mac"] == "AA:BB:CC:DD:EE:FF"


# =============================================================================
# Test BeurerDeviceNotFoundError
# =============================================================================


class TestBeurerDeviceNotFoundError:
    """Tests for BeurerDeviceNotFoundError."""

    def test_inheritance(self) -> None:
        """Test BeurerDeviceNotFoundError inherits from BeurerError."""
        error = BeurerDeviceNotFoundError("Test Lamp", "AA:BB:CC:DD:EE:FF")
        assert isinstance(error, BeurerError)

    def test_translation_key(self) -> None:
        """Test translation key is device_not_found."""
        error = BeurerDeviceNotFoundError("Test Lamp", "AA:BB:CC:DD:EE:FF")
        assert error.translation_key == "device_not_found"

    def test_placeholders(self) -> None:
        """Test placeholders include name and MAC."""
        error = BeurerDeviceNotFoundError("TL100", "11:22:33:44:55:66")
        assert error.translation_placeholders["name"] == "TL100"
        assert error.translation_placeholders["mac"] == "11:22:33:44:55:66"


# =============================================================================
# Test BeurerCommandError
# =============================================================================


class TestBeurerCommandError:
    """Tests for BeurerCommandError."""

    def test_inheritance(self) -> None:
        """Test BeurerCommandError inherits from BeurerError."""
        error = BeurerCommandError("Test Lamp")
        assert isinstance(error, BeurerError)

    def test_translation_key(self) -> None:
        """Test translation key is command_failed."""
        error = BeurerCommandError("Test Lamp")
        assert error.translation_key == "command_failed"

    def test_placeholders(self) -> None:
        """Test placeholders include name."""
        error = BeurerCommandError("TL50")
        assert error.translation_placeholders["name"] == "TL50"


# =============================================================================
# Test BeurerWriteError
# =============================================================================


class TestBeurerWriteError:
    """Tests for BeurerWriteError."""

    def test_inheritance(self) -> None:
        """Test BeurerWriteError inherits from BeurerError."""
        error = BeurerWriteError("Test Lamp")
        assert isinstance(error, BeurerError)

    def test_translation_key(self) -> None:
        """Test translation key is write_failed."""
        error = BeurerWriteError("Test Lamp")
        assert error.translation_key == "write_failed"

    def test_placeholders(self) -> None:
        """Test placeholders include name."""
        error = BeurerWriteError("Beurer TL100")
        assert error.translation_placeholders["name"] == "Beurer TL100"


# =============================================================================
# Test BeurerTimerError
# =============================================================================


class TestBeurerTimerError:
    """Tests for BeurerTimerError."""

    def test_inheritance(self) -> None:
        """Test BeurerTimerError inherits from BeurerError."""
        error = BeurerTimerError("Test Lamp")
        assert isinstance(error, BeurerError)

    def test_default_translation_key(self) -> None:
        """Test default translation key is timer_failed."""
        error = BeurerTimerError("Test Lamp")
        assert error.translation_key == "timer_failed"

    def test_custom_translation_key(self) -> None:
        """Test custom reason becomes translation key."""
        error = BeurerTimerError("Test Lamp", reason="timer_invalid_duration")
        assert error.translation_key == "timer_invalid_duration"

    def test_placeholders(self) -> None:
        """Test placeholders include name."""
        error = BeurerTimerError("My Device")
        assert error.translation_placeholders["name"] == "My Device"


# =============================================================================
# Test BeurerDeviceUnavailableError
# =============================================================================


class TestBeurerDeviceUnavailableError:
    """Tests for BeurerDeviceUnavailableError."""

    def test_inheritance(self) -> None:
        """Test BeurerDeviceUnavailableError inherits from BeurerError."""
        error = BeurerDeviceUnavailableError("Test Lamp")
        assert isinstance(error, BeurerError)

    def test_translation_key(self) -> None:
        """Test translation key is device_unavailable."""
        error = BeurerDeviceUnavailableError("Test Lamp")
        assert error.translation_key == "device_unavailable"

    def test_placeholders(self) -> None:
        """Test placeholders include name."""
        error = BeurerDeviceUnavailableError("Living Room Lamp")
        assert error.translation_placeholders["name"] == "Living Room Lamp"


# =============================================================================
# Test BeurerReconnectError
# =============================================================================


class TestBeurerReconnectError:
    """Tests for BeurerReconnectError."""

    def test_inheritance(self) -> None:
        """Test BeurerReconnectError inherits from BeurerError."""
        error = BeurerReconnectError("Test Lamp")
        assert isinstance(error, BeurerError)

    def test_translation_key(self) -> None:
        """Test translation key is reconnect_failed."""
        error = BeurerReconnectError("Test Lamp")
        assert error.translation_key == "reconnect_failed"

    def test_placeholders(self) -> None:
        """Test placeholders include name."""
        error = BeurerReconnectError("Bedroom Lamp")
        assert error.translation_placeholders["name"] == "Bedroom Lamp"


# =============================================================================
# Test BeurerInitializationError
# =============================================================================


class TestBeurerInitializationError:
    """Tests for BeurerInitializationError."""

    def test_inheritance(self) -> None:
        """Test BeurerInitializationError inherits from BeurerError."""
        error = BeurerInitializationError("Test Lamp", "AA:BB:CC", "Failed to connect")
        assert isinstance(error, BeurerError)

    def test_translation_key(self) -> None:
        """Test translation key is initialization_failed."""
        error = BeurerInitializationError("Test Lamp", "AA:BB:CC", "Error details")
        assert error.translation_key == "initialization_failed"

    def test_placeholders(self) -> None:
        """Test placeholders include name, mac, and error."""
        error = BeurerInitializationError(
            "TL100", "AA:BB:CC:DD:EE:FF", "BLE adapter not found"
        )
        assert error.translation_placeholders["name"] == "TL100"
        assert error.translation_placeholders["mac"] == "AA:BB:CC:DD:EE:FF"
        assert error.translation_placeholders["error"] == "BLE adapter not found"


# =============================================================================
# Test Exception Raising
# =============================================================================


class TestExceptionRaising:
    """Tests for exception raising behavior."""

    def test_can_raise_beurer_error(self) -> None:
        """Test BeurerError can be raised and caught."""
        with pytest.raises(BeurerError):
            raise BeurerError("test_error")

    def test_can_catch_as_homeassistant_error(self) -> None:
        """Test Beurer errors can be caught as HomeAssistantError."""
        with pytest.raises(HomeAssistantError):
            raise BeurerConnectionError("Test")

    def test_can_catch_subclass_as_beurer_error(self) -> None:
        """Test subclasses can be caught as BeurerError."""
        with pytest.raises(BeurerError):
            raise BeurerDeviceNotFoundError("Test", "AA:BB:CC")

        with pytest.raises(BeurerError):
            raise BeurerCommandError("Test")

        with pytest.raises(BeurerError):
            raise BeurerWriteError("Test")

        with pytest.raises(BeurerError):
            raise BeurerTimerError("Test")

        with pytest.raises(BeurerError):
            raise BeurerDeviceUnavailableError("Test")

        with pytest.raises(BeurerError):
            raise BeurerReconnectError("Test")

        with pytest.raises(BeurerError):
            raise BeurerInitializationError("Test", "AA:BB", "Error")
