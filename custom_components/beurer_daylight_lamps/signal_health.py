"""Detect a weak or unstable Bluetooth link to a lamp.

Pure logic without Home Assistant imports, so it is easy to test. The
instance feeds it RSSI readings and reconnects and turns its verdict into a
repair issue.
"""

from __future__ import annotations

from collections import deque

from .const import (
    FREQUENT_RECONNECT_THRESHOLD,
    FREQUENT_RECONNECT_WINDOW,
    WEAK_SIGNAL_DURATION,
    WEAK_SIGNAL_RECOVERED_RSSI,
    WEAK_SIGNAL_RSSI,
)

PROBLEM_WEAK_SIGNAL = "weak_signal"
PROBLEM_FREQUENT_RECONNECTS = "frequent_reconnects"


class SignalHealthMonitor:
    """Track RSSI and reconnects and report a lasting connection problem.

    - Weak signal: every reading for WEAK_SIGNAL_DURATION seconds was at or
      below WEAK_SIGNAL_RSSI. It clears once a reading reaches
      WEAK_SIGNAL_RECOVERED_RSSI (hysteresis, so the issue does not flap).
    - Frequent reconnects: at least FREQUENT_RECONNECT_THRESHOLD reconnects
      within FREQUENT_RECONNECT_WINDOW seconds. It clears once the window
      holds fewer reconnects.
    """

    def __init__(self) -> None:
        """Initialize the monitor."""
        self._weak_since: float | None = None
        self._weak_signal = False
        self._reconnects: deque[float] = deque()
        self.last_rssi: int | None = None

    def record_rssi(self, rssi: int, now: float) -> None:
        """Record a signal strength reading."""
        self.last_rssi = rssi
        if rssi <= WEAK_SIGNAL_RSSI:
            if self._weak_since is None:
                self._weak_since = now
            if now - self._weak_since >= WEAK_SIGNAL_DURATION:
                self._weak_signal = True
        elif rssi >= WEAK_SIGNAL_RECOVERED_RSSI:
            self._weak_since = None
            self._weak_signal = False
        else:
            # Between the thresholds: no longer weak enough to start the
            # timer, not yet strong enough to clear an active problem.
            self._weak_since = None

    def record_reconnect(self, now: float) -> None:
        """Record a reconnect after a lost connection."""
        self._reconnects.append(now)
        self._prune(now)

    def reconnects_in_window(self, now: float) -> int:
        """Return the number of reconnects within the window."""
        self._prune(now)
        return len(self._reconnects)

    def problem(self, now: float) -> str | None:
        """Return the current problem, or None when the link is healthy."""
        if self._weak_signal:
            return PROBLEM_WEAK_SIGNAL
        if self.reconnects_in_window(now) >= FREQUENT_RECONNECT_THRESHOLD:
            return PROBLEM_FREQUENT_RECONNECTS
        return None

    def _prune(self, now: float) -> None:
        while (
            self._reconnects and now - self._reconnects[0] > FREQUENT_RECONNECT_WINDOW
        ):
            self._reconnects.popleft()
